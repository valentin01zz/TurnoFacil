from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core import mail
from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from billing.models import Plan, Subscription, TrialNotice
from billing.notices import due_notice, run_billing_tasks
from billing.payments import ManualProvider, PaymentProvider, confirm_payment
from billing.services import choose_plan
from bookings.tests.helpers import create_business

from .helpers import end_trial, set_active


class PlansPageTests(TestCase):
    def setUp(self):
        self.business = create_business()
        self.client.force_login(self.business.owner)

    def test_shows_copy_plans_prices_limits_and_trial(self):
        response = self.client.get(reverse("plans"))

        for text in [
            "Elegí el plan ideal para tu negocio",
            "Administrá tus turnos, organizá a tus profesionales y permití que tus clientes "
            "reserven online.",
            "Probá gratis durante 14 días. Sin tarjeta de crédito y sin compromiso.",
            "$ 14.900",
            "$ 24.900",
            "$ 39.900",
            "ARS por mes",
            "Hasta 1 profesional activo",
            "Hasta 5 profesionales activos",
            "Hasta 15 profesionales activos",
            "Página de reservas online para tus clientes",
            "Prueba activa",
            "Tu prueba",
        ]:
            self.assertContains(response, text)
        self.assertNotContains(response, "Piloto")

    def test_choosing_records_the_choice_and_explains_the_next_step(self):
        response = self.client.post(reverse("choose_plan", args=["negocio"]), follow=True)

        self.assertContains(response, "Listo, elegiste el plan Negocio")
        self.assertContains(response, "Falta activar el pago")
        self.assertContains(response, "Elegido")

    def test_choose_requires_post(self):
        self.assertEqual(self.client.get(reverse("choose_plan", args=["negocio"])).status_code, 405)

    def test_expired_trial_shows_end_date_and_read_only_policy(self):
        end_trial(self.business)

        response = self.client.get(reverse("plans"))

        self.assertContains(response, "Prueba vencida")
        self.assertContains(response, "Tu prueba gratis terminó el")
        self.assertContains(response, "modo lectura")

    def test_price_changes_show_up_without_code_changes(self):
        call_command("set_plan", "esencial", "--price", "15900", stdout=StringIO())

        self.assertContains(self.client.get(reverse("plans")), "$ 15.900")


class TrialNoticeTests(TestCase):
    def setUp(self):
        self.business = create_business(name="Estética Luna")
        self.subscription = self.business.subscription

    def ends_in(self, delta):
        now = timezone.now()
        Subscription.objects.filter(pk=self.subscription.pk).update(
            trial_started_at=now + delta - timedelta(days=14), trial_ends_at=now + delta
        )
        self.subscription.refresh_from_db()

    def test_kind_by_time_left(self):
        now = timezone.now()
        cases = [
            (timedelta(days=10), None),
            (timedelta(days=6, hours=20), TrialNotice.DAYS_7),
            (timedelta(days=2, hours=5), TrialNotice.DAYS_3),
            (timedelta(hours=20), TrialNotice.DAYS_1),
            (-timedelta(minutes=1), TrialNotice.ENDED),
        ]
        for delta, expected in cases:
            self.subscription.trial_ends_at = now + delta
            self.assertEqual(due_notice(self.subscription, now), expected, delta)

    def test_each_notice_is_sent_once_to_the_owner(self):
        self.ends_in(timedelta(days=6))

        self.assertEqual(run_billing_tasks(), 1)
        self.assertEqual(run_billing_tasks(), 0)

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [self.business.owner.email])
        self.assertEqual(message.subject, "Te quedan 7 días de prueba en TurnoFacil")
        self.assertIn("Estética Luna", message.body)
        self.assertIn("/panel/planes/", message.body)

    def test_all_four_notices_over_the_trial(self):
        for delta in (
            timedelta(days=6),
            timedelta(days=2),
            timedelta(hours=12),
            -timedelta(hours=1),
        ):
            self.ends_in(delta)
            run_billing_tasks()

        kinds = set(TrialNotice.objects.values_list("kind", flat=True))
        self.assertEqual(kinds, {"days_7", "days_3", "days_1", "ended"})
        self.assertEqual(mail.outbox[-1].subject, "Terminó tu prueba de TurnoFacil")
        self.assertIn("modo lectura", mail.outbox[-1].body)

    def test_after_downtime_only_the_most_urgent_is_sent(self):
        self.ends_in(timedelta(hours=10))

        run_billing_tasks()

        self.assertEqual(list(TrialNotice.objects.values_list("kind", flat=True)), ["days_1"])

    def test_active_subscriptions_get_no_trial_notices(self):
        self.ends_in(timedelta(days=2))
        set_active(self.business, "negocio")

        self.assertEqual(run_billing_tasks(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_failed_send_is_retried(self):
        self.ends_in(timedelta(days=2))

        with (
            mock.patch("billing.notices.send_mail", side_effect=OSError("smtp down")),
            self.assertLogs("billing.notices", level="ERROR"),
        ):
            self.assertEqual(run_billing_tasks(), 0)
        self.assertFalse(TrialNotice.objects.exists())

        self.assertEqual(run_billing_tasks(), 1)

    def test_database_enforces_one_notice_per_kind(self):
        TrialNotice.objects.create(subscription=self.subscription, kind=TrialNotice.DAYS_7)

        with self.assertRaises(IntegrityError):
            TrialNotice.objects.create(subscription=self.subscription, kind=TrialNotice.DAYS_7)


class FakeProvider(PaymentProvider):
    name = "fake"

    def verify_confirmation(self, payload):
        if payload.get("signature") != "valid":
            raise ValueError("signature mismatch")
        return payload["id"], timezone.now() + timedelta(days=30)


class PaymentInterfaceTests(TestCase):
    def setUp(self):
        self.business = create_business()

    def test_manual_provider_never_activates(self):
        subscription = choose_plan(self.business.subscription, Plan.objects.get(code="negocio"))

        result = ManualProvider().start_checkout(subscription, subscription.selected_plan)

        self.assertIsNone(result.redirect_url)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, Subscription.PENDING_PAYMENT)

    def test_only_a_verified_confirmation_activates(self):
        subscription = choose_plan(self.business.subscription, Plan.objects.get(code="negocio"))
        Subscription.objects.filter(pk=subscription.pk).update(
            provider="fake", provider_subscription_id="sub_123"
        )

        with self.assertRaises(ValueError):
            confirm_payment(FakeProvider(), {"id": "sub_123", "signature": "forged"})
        self.assertEqual(Subscription.objects.get(pk=subscription.pk).status, "pending_payment")

        confirm_payment(FakeProvider(), {"id": "sub_123", "signature": "valid"})

        subscription.refresh_from_db()
        self.assertEqual(subscription.status, Subscription.ACTIVE)
        self.assertEqual(subscription.plan.code, "negocio")
        self.assertIsNotNone(subscription.current_period_end)

    def test_provider_references_are_unique(self):
        other = create_business("b@example.com", "Otro")
        Subscription.objects.filter(business=self.business).update(
            provider="fake", provider_subscription_id="sub_1"
        )

        with self.assertRaises(IntegrityError):
            Subscription.objects.filter(business=other).update(
                provider="fake", provider_subscription_id="sub_1"
            )

    @override_settings(
        PAYMENT_PROVIDER="billing.tests.test_plans_page_notices_payments.RedirectProvider"
    )
    def test_a_provider_can_redirect_to_its_checkout(self):
        self.client.force_login(self.business.owner)

        response = self.client.post(reverse("choose_plan", args=["negocio"]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "https://pagos.example/checkout/negocio")


class RedirectProvider(PaymentProvider):
    name = "redirect"

    def start_checkout(self, subscription, plan):
        from billing.payments import CheckoutResult

        return CheckoutResult(f"https://pagos.example/checkout/{plan.code}", "")
