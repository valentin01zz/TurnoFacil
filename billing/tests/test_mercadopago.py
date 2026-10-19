import hashlib
import hmac
import json
from datetime import timedelta
from datetime import timezone as dt_timezone
from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from billing.access import get_access
from billing.mercadopago import (
    MercadoPagoProvider,
    apply_payment,
    external_reference,
    valid_signature,
)
from billing.models import Plan, Subscription
from billing.payments import PaymentError, reconcile_subscriptions
from billing.services import add_months, choose_plan, set_provider_reference
from bookings.tests.helpers import create_business, create_professional

from .helpers import end_trial, set_active

SECRET = "test-webhook-secret"
PROVIDER = "billing.tests.test_mercadopago.FakeMercadoPagoProvider"


class FakeClient:
    """Stands in for Mercado Pago's API: records calls and answers from in-memory data."""

    def __init__(self):
        self.calls = []
        self.preapprovals = {}
        self.payments = {}
        self.fail = False
        self.next_id = 1

    def _call(self, *call):
        self.calls.append(call)
        if self.fail:
            raise PaymentError("Mercado Pago no responde")

    def create_preapproval(self, body):
        self._call("create", body)
        preapproval_id = f"pre_{self.next_id}"
        self.next_id += 1
        self.preapprovals[preapproval_id] = {
            "id": preapproval_id,
            "status": "pending",
            "external_reference": body["external_reference"],
            "auto_recurring": dict(body["auto_recurring"]),
        }
        return {
            "id": preapproval_id,
            "init_point": f"https://mp.example/checkout?preapproval_id={preapproval_id}",
        }

    def get_preapproval(self, preapproval_id):
        self._call("get", preapproval_id)
        if preapproval_id not in self.preapprovals:
            raise PaymentError("404")
        return dict(self.preapprovals[preapproval_id])

    def update_preapproval(self, preapproval_id, body):
        self._call("update", preapproval_id, body)
        self.preapprovals.setdefault(preapproval_id, {"id": preapproval_id}).update(body)
        return self.preapprovals[preapproval_id]

    def get_authorized_payment(self, payment_id):
        self._call("get_payment", payment_id)
        if payment_id not in self.payments:
            raise PaymentError("404")
        return dict(self.payments[payment_id])


FAKE = FakeClient()


class FakeMercadoPagoProvider(MercadoPagoProvider):
    def __init__(self, client=None):
        super().__init__(client=FAKE)


def sign(data_id, request_id="req-1", ts="1760000000", secret=SECRET):
    manifest = f"id:{data_id.lower()};request-id:{request_id};ts:{ts};"
    digest = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return f"ts={ts},v1={digest}"


class SignatureTests(TestCase):
    def test_valid_signature(self):
        self.assertTrue(valid_signature(SECRET, sign("123"), "req-1", "123"))

    def test_alphanumeric_ids_are_lowercased_like_mercado_pago_does(self):
        self.assertTrue(valid_signature(SECRET, sign("abc123"), "req-1", "ABC123"))

    def test_rejects_tampering_and_missing_parts(self):
        header = sign("123")
        self.assertFalse(valid_signature(SECRET, header, "req-1", "124"))
        self.assertFalse(valid_signature(SECRET, header, "req-2", "123"))
        self.assertFalse(valid_signature("otro-secreto", header, "req-1", "123"))
        self.assertFalse(valid_signature(SECRET, "ts=1760000000", "req-1", "123"))
        self.assertFalse(valid_signature(SECRET, "", "req-1", "123"))
        self.assertFalse(valid_signature("", header, "req-1", "123"))


@override_settings(
    PAYMENT_PROVIDER=PROVIDER,
    MERCADOPAGO_WEBHOOK_SECRET=SECRET,
    SITE_URL="https://turnofacil.example",
)
class MercadoPagoTestCase(TestCase):
    def setUp(self):
        FAKE.__init__()
        self.business = create_business(name="Estética Luna")
        self.subscription = self.business.subscription
        self.client.force_login(self.business.owner)

    def refresh(self):
        self.subscription.refresh_from_db()
        return self.subscription

    def checkout(self, code="negocio", email="pagos@luna.example"):
        return self.client.post(reverse("checkout", args=[code]), {"payer_email": email})

    def notify(self, topic, resource_id, header=None):
        return self.client.post(
            f"{reverse('mercadopago_webhook')}?data.id={resource_id}&type={topic}",
            data=json.dumps({"type": topic, "data": {"id": resource_id}}),
            content_type="application/json",
            headers={
                "x-signature": header if header is not None else sign(resource_id),
                "x-request-id": "req-1",
            },
        )

    def authorize(self, preapproval_id="pre_1", next_payment=None):
        next_payment = next_payment or self.refresh().trial_ends_at
        FAKE.preapprovals[preapproval_id].update(
            status="authorized", next_payment_date=next_payment.isoformat()
        )
        return self.notify("subscription_preapproval", preapproval_id)

    def subscribed(self, code="negocio"):
        """A subscription that went through checkout and was authorized at Mercado Pago."""
        self.checkout(code)
        self.authorize()
        return self.refresh()

    def charge(self, payment_id, status, debit_date, preapproval_id="pre_1"):
        FAKE.payments[payment_id] = {
            "id": payment_id,
            "preapproval_id": preapproval_id,
            "debit_date": debit_date.isoformat(),
            "payment": {"id": 9000, "status": status},
        }
        return self.notify("subscription_authorized_payment", payment_id)


class CheckoutTests(MercadoPagoTestCase):
    def test_choosing_a_plan_goes_to_the_checkout_page(self):
        response = self.client.post(reverse("choose_plan", args=["negocio"]))

        self.assertRedirects(response, reverse("checkout", args=["negocio"]))
        self.assertEqual(self.refresh().status, Subscription.TRIALING)
        self.assertEqual(FAKE.calls, [])

    def test_checkout_page_shows_price_first_charge_and_owner_email(self):
        response = self.client.get(reverse("checkout", args=["negocio"]))

        self.assertContains(response, "Plan Negocio")
        self.assertContains(response, "$ 39.900")
        self.assertContains(response, "No te cobramos nada hoy")
        self.assertContains(response, "Email de tu cuenta de Mercado Pago")
        self.assertContains(response, self.business.owner.email)

    def test_checkout_in_trial_charges_first_when_the_trial_ends(self):
        response = self.checkout()

        self.assertRedirects(
            response,
            "https://mp.example/checkout?preapproval_id=pre_1",
            fetch_redirect_response=False,
        )
        body = FAKE.calls[0][1]
        subscription = self.refresh()
        self.assertEqual(body["status"], "pending")
        self.assertEqual(body["payer_email"], "pagos@luna.example")
        self.assertEqual(body["external_reference"], external_reference(subscription))
        self.assertEqual(body["back_url"], "https://turnofacil.example/panel/planes/pago/")
        recurring = body["auto_recurring"]
        self.assertEqual(recurring["transaction_amount"], 39900.0)
        self.assertEqual(recurring["currency_id"], "ARS")
        self.assertEqual((recurring["frequency"], recurring["frequency_type"]), (1, "months"))
        self.assertEqual(
            recurring["start_date"],
            subscription.trial_ends_at.astimezone(dt_timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.000Z"
            ),
        )
        self.assertEqual(subscription.status, Subscription.PENDING_PAYMENT)
        self.assertEqual(subscription.selected_plan.code, "negocio")
        self.assertEqual(
            (subscription.provider, subscription.provider_subscription_id),
            (
                "mercadopago",
                "pre_1",
            ),
        )
        # Starting the checkout grants nothing: the trial goes on with its own plan.
        self.assertEqual(get_access(self.business).plan.code, "profesional")

    def test_after_the_trial_the_first_charge_is_now(self):
        end_trial(self.business)

        self.checkout()

        self.assertNotIn("start_date", FAKE.calls[0][1]["auto_recurring"])

    def test_mercado_pago_failure_changes_nothing(self):
        FAKE.fail = True

        with self.assertLogs("billing.views", level="ERROR"):
            response = self.checkout()

        self.assertContains(response, "No pudimos conectarnos con Mercado Pago")
        subscription = self.refresh()
        self.assertEqual(subscription.status, Subscription.TRIALING)
        self.assertEqual(subscription.provider_subscription_id, "")

    def test_plan_limit_is_checked_before_calling_mercado_pago(self):
        create_professional(self.business, name="Ana")
        create_professional(self.business, name="Bea")

        response = self.checkout("esencial")

        self.assertRedirects(response, reverse("plans"))
        self.assertEqual(FAKE.calls, [])

    def test_a_new_checkout_discards_the_abandoned_one(self):
        self.checkout("negocio")
        self.checkout("esencial")

        self.assertEqual(self.refresh().provider_subscription_id, "pre_2")
        self.assertIn(("update", "pre_1", {"status": "cancelled"}), FAKE.calls)

    def test_invalid_email_is_rejected(self):
        response = self.checkout(email="no-es-un-email")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(FAKE.calls, [])


class WebhookTests(MercadoPagoTestCase):
    def test_authorization_activates_until_the_first_charge(self):
        self.checkout()
        trial_ends_at = self.refresh().trial_ends_at

        response = self.authorize()

        self.assertEqual(response.status_code, 200)
        subscription = self.refresh()
        self.assertEqual(subscription.status, Subscription.ACTIVE)
        self.assertEqual(subscription.plan.code, "negocio")
        self.assertIsNone(subscription.selected_plan)
        self.assertEqual(subscription.current_period_end, trial_ends_at)
        self.assertTrue(subscription.renews_automatically)
        self.assertEqual(get_access(self.business).plan.code, "negocio")

    def test_the_state_is_read_from_the_api_not_from_the_notification(self):
        self.checkout()  # still "pending" at Mercado Pago

        self.notify("subscription_preapproval", "pre_1")

        self.assertEqual(self.refresh().status, Subscription.PENDING_PAYMENT)
        self.assertIn(("get", "pre_1"), FAKE.calls)

    def test_repeated_notifications_change_nothing(self):
        self.subscribed()
        events = self.subscription.events.count()

        self.authorize()
        self.authorize()

        self.assertEqual(self.subscription.events.count(), events)

    def test_invalid_signature_is_rejected_before_calling_the_api(self):
        self.checkout()
        FAKE.preapprovals["pre_1"]["status"] = "authorized"
        FAKE.calls.clear()

        response = self.notify(
            "subscription_preapproval", "pre_1", header=sign("pre_1", secret="otro-secreto")
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(FAKE.calls, [])
        self.assertEqual(self.refresh().status, Subscription.PENDING_PAYMENT)

    @override_settings(MERCADOPAGO_WEBHOOK_SECRET="")
    def test_without_a_secret_nothing_is_processed(self):
        with self.assertLogs("billing.views", level="ERROR"):
            response = self.notify("subscription_preapproval", "pre_1")

        self.assertEqual(response.status_code, 503)

    @override_settings(PAYMENT_PROVIDER="billing.payments.ManualProvider")
    def test_webhook_is_off_without_mercado_pago(self):
        self.assertEqual(self.notify("subscription_preapproval", "pre_1").status_code, 404)

    def test_webhook_only_accepts_post(self):
        self.assertEqual(self.client.get(reverse("mercadopago_webhook")).status_code, 405)

    def test_unknown_resources_are_acknowledged_and_ignored(self):
        FAKE.preapprovals["pre_99"] = {
            "id": "pre_99",
            "status": "authorized",
            "external_reference": "turnofacil-sub-999",
        }

        response = self.notify("subscription_preapproval", "pre_99")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.refresh().status, Subscription.TRIALING)

    def test_a_preapproval_for_another_subscription_is_ignored(self):
        self.checkout()
        FAKE.preapprovals["pre_1"].update(
            status="authorized", external_reference="turnofacil-sub-999"
        )

        with self.assertLogs("billing.mercadopago", level="WARNING"):
            self.notify("subscription_preapproval", "pre_1")

        self.assertEqual(self.refresh().status, Subscription.PENDING_PAYMENT)

    def test_api_errors_ask_mercado_pago_to_retry(self):
        FAKE.fail = True

        with self.assertLogs("billing.views", level="WARNING"):
            response = self.notify("subscription_preapproval", "pre_1")

        self.assertEqual(response.status_code, 502)

    def test_other_topics_are_acknowledged(self):
        self.assertEqual(self.notify("payment", "123").status_code, 200)
        self.assertEqual(FAKE.calls, [])


class ChargeTests(MercadoPagoTestCase):
    def test_approved_charge_pays_one_month_from_its_date(self):
        self.subscribed()
        debit = timezone.now()

        self.charge("ap_1", "approved", debit)

        subscription = self.refresh()
        self.assertEqual(subscription.status, Subscription.ACTIVE)
        self.assertEqual(subscription.current_period_end, add_months(debit, 1))

    def test_the_same_charge_twice_counts_once(self):
        self.subscribed()
        debit = timezone.now()
        self.charge("ap_1", "approved", debit)
        events = self.subscription.events.count()

        self.charge("ap_1", "approved", debit)

        self.assertEqual(self.subscription.events.count(), events)
        self.assertEqual(self.refresh().current_period_end, add_months(debit, 1))

    def test_rejected_charge_is_past_due_with_grace_then_recovers(self):
        self.subscribed()
        period_end = self.refresh().current_period_end

        self.charge("ap_1", "rejected", period_end)

        self.assertEqual(self.refresh().status, Subscription.PAST_DUE)
        self.assertFalse(get_access(self.business, now=period_end + timedelta(days=2)).read_only)
        self.assertTrue(get_access(self.business, now=period_end + timedelta(days=4)).read_only)

        self.charge("ap_2", "approved", period_end + timedelta(days=1))

        subscription = self.refresh()
        self.assertEqual(subscription.status, Subscription.ACTIVE)
        self.assertEqual(
            subscription.current_period_end, add_months(period_end + timedelta(days=1), 1)
        )

    def test_charges_for_unknown_subscriptions_are_ignored(self):
        FAKE.payments["ap_9"] = {
            "id": "ap_9",
            "preapproval_id": "pre_77",
            "payment": {"status": "approved"},
        }

        self.assertEqual(self.notify("subscription_authorized_payment", "ap_9").status_code, 200)
        self.assertEqual(self.refresh().status, Subscription.TRIALING)

    def test_an_approved_charge_never_reopens_a_closed_subscription(self):
        subscription = self.subscribed()
        Subscription.objects.filter(pk=subscription.pk).update(status=Subscription.CANCELED)

        with self.assertLogs("billing.mercadopago", level="WARNING"):
            apply_payment(
                self.refresh(),
                {"preapproval_id": "pre_1", "payment": {"status": "approved"}},
            )

        self.assertEqual(self.refresh().status, Subscription.CANCELED)


class CancelAndChangeTests(MercadoPagoTestCase):
    def test_plans_page_shows_next_charge_and_cancel_link(self):
        self.subscribed()

        response = self.client.get(reverse("plans"))

        self.assertContains(response, "se paga solo con Mercado Pago")
        self.assertContains(response, "Próximo cobro")
        self.assertContains(response, reverse("cancel_subscription"))

    def test_cancel_keeps_access_until_the_paid_period_ends(self):
        subscription = self.subscribed()
        period_end = subscription.current_period_end

        self.assertContains(self.client.get(reverse("cancel_subscription")), "Sí, dar de baja")
        self.client.post(reverse("cancel_subscription"))

        subscription = self.refresh()
        self.assertIn(("update", "pre_1", {"status": "cancelled"}), FAKE.calls)
        self.assertEqual(subscription.status, Subscription.ACTIVE)
        self.assertIsNotNone(subscription.canceled_at)
        self.assertFalse(subscription.renews_automatically)
        self.assertFalse(get_access(self.business).read_only)
        self.assertTrue(get_access(self.business, now=period_end + timedelta(minutes=1)).read_only)
        self.assertContains(self.client.get(reverse("plans")), "Diste de baja tu suscripción")

        result = reconcile_subscriptions(now=period_end + timedelta(minutes=1))

        self.assertEqual(result["closed"], 1)
        self.assertEqual(self.refresh().status, Subscription.CANCELED)

    def test_cancel_fails_cleanly_when_mercado_pago_is_down(self):
        self.subscribed()
        FAKE.fail = True

        with self.assertLogs("billing.views", level="ERROR"):
            response = self.client.post(reverse("cancel_subscription"), follow=True)

        self.assertContains(response, "No pudimos dar de baja")
        self.assertIsNone(self.refresh().canceled_at)

    def test_cancellation_at_mercado_pago_is_followed(self):
        self.subscribed()
        FAKE.preapprovals["pre_1"]["status"] = "cancelled"

        self.notify("subscription_preapproval", "pre_1")

        subscription = self.refresh()
        self.assertEqual(subscription.status, Subscription.ACTIVE)
        self.assertIsNotNone(subscription.canceled_at)

    def test_past_due_canceled_at_mercado_pago_closes(self):
        subscription = self.subscribed()
        self.charge("ap_1", "rejected", subscription.current_period_end)
        FAKE.preapprovals["pre_1"]["status"] = "cancelled"

        self.notify("subscription_preapproval", "pre_1")

        self.assertEqual(self.refresh().status, Subscription.CANCELED)

    def test_cancel_page_needs_a_renewing_subscription(self):
        self.assertRedirects(self.client.get(reverse("cancel_subscription")), reverse("plans"))

    def test_resubscribing_after_cancel_starts_charging_when_the_paid_time_ends(self):
        subscription = self.subscribed()
        period_end = subscription.current_period_end
        self.client.post(reverse("cancel_subscription"))

        self.checkout("negocio")

        expected = period_end.astimezone(dt_timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        self.assertEqual(
            [c for c in FAKE.calls if c[0] == "create"][-1][1]["auto_recurring"]["start_date"],
            expected,
        )
        # The time already paid for is kept while the new checkout is pending.
        self.assertEqual(get_access(self.business).plan.code, "negocio")

    def test_changing_plan_updates_the_price_at_mercado_pago(self):
        self.subscribed("negocio")

        response = self.client.post(reverse("choose_plan", args=["esencial"]), follow=True)

        self.assertContains(response, "ya tenés el plan Esencial")
        self.assertIn(
            (
                "update",
                "pre_1",
                {
                    "reason": "TurnoFacil Esencial - Estética Luna",
                    "auto_recurring": {"transaction_amount": 14900.0, "currency_id": "ARS"},
                },
            ),
            FAKE.calls,
        )
        subscription = self.refresh()
        self.assertEqual(subscription.plan.code, "esencial")
        self.assertEqual(subscription.status, Subscription.ACTIVE)

    def test_changing_to_a_plan_too_small_calls_nothing(self):
        self.subscribed("negocio")
        create_professional(self.business, name="Ana")
        create_professional(self.business, name="Bea")
        FAKE.calls.clear()

        response = self.client.post(reverse("choose_plan", args=["esencial"]), follow=True)

        self.assertContains(response, "desactivá")
        self.assertEqual(FAKE.calls, [])
        self.assertEqual(self.refresh().plan.code, "negocio")


class ReconciliationTests(MercadoPagoTestCase):
    def test_a_missed_authorization_is_caught_by_the_scheduled_task(self):
        self.checkout()
        FAKE.preapprovals["pre_1"].update(
            status="authorized", next_payment_date=self.refresh().trial_ends_at.isoformat()
        )

        result = reconcile_subscriptions()

        self.assertEqual(result["synced"], 1)
        self.assertEqual(self.refresh().status, Subscription.ACTIVE)

    def test_coming_back_from_mercado_pago_checks_right_away(self):
        self.checkout()
        FAKE.preapprovals["pre_1"].update(
            status="authorized", next_payment_date=self.refresh().trial_ends_at.isoformat()
        )

        response = self.client.get(reverse("payment_return"), follow=True)

        self.assertContains(response, "Tu suscripción quedó activa")
        self.assertEqual(self.refresh().status, Subscription.ACTIVE)

    def test_coming_back_before_the_confirmation_explains_the_wait(self):
        self.checkout()

        response = self.client.get(reverse("payment_return"), follow=True)

        self.assertContains(response, "Mercado Pago nos lo confirma en unos minutos")

    def test_a_charge_never_confirmed_becomes_past_due_with_grace(self):
        subscription = self.subscribed()
        period_end = subscription.current_period_end

        # The day it is due, before any confirmation, the owner keeps access.
        self.assertFalse(get_access(self.business, now=period_end + timedelta(hours=6)).read_only)
        self.assertEqual(
            reconcile_subscriptions(now=period_end + timedelta(hours=6))["past_due"], 0
        )

        result = reconcile_subscriptions(now=period_end + timedelta(days=1, minutes=1))

        self.assertEqual(result["past_due"], 1)
        self.assertEqual(self.refresh().status, Subscription.PAST_DUE)

    def test_command_reports_the_upkeep(self):
        out = StringIO()

        call_command("run_billing_tasks", stdout=out)

        self.assertIn("Trial notices sent: 0", out.getvalue())
        self.assertIn("synced with provider: 0", out.getvalue())


@override_settings(PAYMENT_PROVIDER=PROVIDER)
class GrantPlanWithProviderTests(TestCase):
    def setUp(self):
        self.business = create_business()

    def test_refuses_a_business_that_already_pays_automatically(self):
        subscription = set_active(self.business, "negocio", timezone.now() + timedelta(days=10))
        set_provider_reference(subscription, "mercadopago", "pre_1")

        with self.assertRaisesMessage(CommandError, "cancelá ese cobro"):
            call_command("grant_plan", self.business.slug, "negocio", "--months", "1")

    def test_a_transfer_month_extends_the_paid_period(self):
        period_end = timezone.now() + timedelta(days=10)
        set_active(self.business, "negocio", period_end)

        call_command(
            "grant_plan", self.business.slug, "negocio", "--months", "1", stdout=StringIO()
        )

        self.assertEqual(
            Subscription.objects.get(business=self.business).current_period_end,
            add_months(period_end, 1),
        )


class ManualPlanChangeTests(TestCase):
    def test_changing_plan_keeps_the_time_already_paid(self):
        business = create_business()
        subscription = set_active(business, "negocio", timezone.now() + timedelta(days=10))

        choose_plan(subscription, Plan.objects.get(code="esencial"))

        access = get_access(business)
        self.assertFalse(access.read_only)
        self.assertEqual(access.plan.code, "negocio")


@override_settings(
    TRANSFER_ALIAS="turnofacil.pagos",
    TRANSFER_HOLDER="Ana Pérez",
    TRANSFER_CUIT="20-12345678-9",
    BILLING_CONTACT_EMAIL="pagos@turnofacil.example",
)
class TransferTests(TestCase):
    def test_plans_page_shows_the_transfer_details(self):
        business = create_business()
        self.client.force_login(business.owner)

        response = self.client.get(reverse("plans"))

        for text in ("turnofacil.pagos", "Ana Pérez", "20-12345678-9", "pagos@turnofacil.example"):
            self.assertContains(response, text)

    @override_settings(TRANSFER_ALIAS="")
    def test_hidden_without_an_alias(self):
        business = create_business()
        self.client.force_login(business.owner)

        self.assertNotContains(
            self.client.get(reverse("plans")), "Preferís pagar por transferencia"
        )
