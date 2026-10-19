from datetime import timedelta
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from billing.access import get_access
from billing.models import Plan, Subscription
from billing.services import (
    InvalidTransition,
    PlanLimitExceeded,
    activate,
    choose_plan,
    transition,
)
from bookings.models import Appointment
from bookings.reminders import send_due_reminders
from bookings.tests.helpers import (
    create_appointment,
    create_business,
    create_professional,
    create_service,
    future_date,
    local_dt,
)
from businesses.models import Professional, Service

from .helpers import end_trial, set_active


class AccessByStateTests(TestCase):
    def setUp(self):
        self.business = create_business()
        self.subscription = self.business.subscription
        self.now = timezone.now()

    def access(self, now=None):
        return get_access(self.business, now=now)

    def test_trial_over_is_read_only_even_before_the_status_is_updated(self):
        end_trial(self.business)

        access = self.access()

        self.assertEqual(access.status, Subscription.TRIAL_EXPIRED)
        self.assertTrue(access.read_only)
        self.assertFalse(access.can("panel.edit"))

    def test_pending_payment_keeps_the_trial_while_it_lasts(self):
        choose_plan(self.subscription, Plan.objects.get(code="negocio"))

        self.assertFalse(self.access().read_only)
        self.assertEqual(self.access().plan.code, "profesional")
        end_trial(self.business)
        self.assertTrue(self.access().read_only)

    def test_active_until_the_period_ends(self):
        set_active(self.business, "negocio", period_end=self.now + timedelta(days=30))

        self.assertEqual(self.access().plan.code, "negocio")
        self.assertTrue(self.access(now=self.now + timedelta(days=31)).read_only)

    def test_past_due_has_a_short_grace(self):
        set_active(self.business, "esencial", period_end=self.now)
        Subscription.objects.filter(pk=self.subscription.pk).update(status=Subscription.PAST_DUE)

        self.assertFalse(self.access(now=self.now + timedelta(days=2)).read_only)
        self.assertTrue(self.access(now=self.now + timedelta(days=4)).read_only)

    def test_canceled_is_read_only(self):
        set_active(self.business, "esencial", period_end=None)
        transition(Subscription.objects.get(pk=self.subscription.pk), Subscription.CANCELED, "Baja")

        self.assertTrue(self.access().read_only)

    def test_missing_subscription_is_read_only(self):
        Subscription.objects.filter(pk=self.subscription.pk).delete()

        self.assertTrue(get_access(self.business).read_only)


class TransitionTests(TestCase):
    def setUp(self):
        self.business = create_business()
        self.subscription = self.business.subscription

    def test_invalid_transitions_are_rejected(self):
        for to_status in (Subscription.PAST_DUE, Subscription.CANCELED):
            with self.assertRaises(InvalidTransition, msg=to_status):
                transition(self.subscription, to_status, "intento")
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, Subscription.TRIALING)

    def test_transitions_are_logged(self):
        choose_plan(self.subscription, Plan.objects.get(code="esencial"))

        event = self.subscription.events.last()
        self.assertEqual((event.from_status, event.to_status), ("trialing", "pending_payment"))
        self.assertIn("Esencial", event.reason)

    def test_choosing_a_plan_never_marks_it_paid(self):
        subscription = choose_plan(self.subscription, Plan.objects.get(code="negocio"))

        self.assertEqual(subscription.status, Subscription.PENDING_PAYMENT)
        self.assertEqual(subscription.plan.code, "profesional")
        self.assertEqual(subscription.selected_plan.code, "negocio")

    def test_expiry_command_updates_the_status(self):
        end_trial(self.business)

        call_command("run_billing_tasks", stdout=StringIO())

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, Subscription.TRIAL_EXPIRED)
        self.assertEqual(self.subscription.events.last().reason, "La prueba terminó")

    def test_owner_cannot_force_a_status_through_the_form(self):
        self.client.force_login(self.business.owner)

        self.client.post(
            reverse("choose_plan", args=["esencial"]),
            {"status": "active", "plan": "negocio", "trial_ends_at": "2099-01-01"},
        )

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, Subscription.PENDING_PAYMENT)
        self.assertEqual(self.subscription.selected_plan.code, "esencial")
        self.assertNotEqual(self.subscription.trial_ends_at.year, 2099)


class ReadOnlyEnforcementTests(TestCase):
    def setUp(self):
        self.business = create_business(name="Estética Luna")
        self.ana = create_professional(self.business, name="Ana")
        self.service = create_service(self.business, name="Limpieza facial")
        self.appointment = create_appointment(self.ana, self.service, local_dt(future_date(), 10))
        end_trial(self.business)
        self.client.force_login(self.business.owner)

    def test_every_editing_route_is_blocked_on_the_server(self):
        routes = [
            reverse("business_edit"),
            reverse("service_create"),
            reverse("service_edit", args=[self.service.pk]),
            reverse("professional_create"),
            reverse("professional_edit", args=[self.ana.pk]),
            reverse("appointment_create"),
            reverse("appointment_reschedule", args=[self.appointment.pk]),
            reverse("appointment_cancel", args=[self.appointment.pk]),
        ]
        for url in routes:
            for method in (self.client.get, self.client.post):
                response = method(url, {"name": "Hackeado", "duration_minutes": 5, "address": "x"})
                self.assertRedirects(response, reverse("plans"), msg_prefix=url)

        self.business.refresh_from_db()
        self.service.refresh_from_db()
        self.appointment.refresh_from_db()
        self.assertEqual(self.business.name, "Estética Luna")
        self.assertEqual(self.service.name, "Limpieza facial")
        self.assertEqual(Service.objects.filter(business=self.business).count(), 1)
        self.assertEqual(Professional.objects.filter(business=self.business).count(), 1)
        self.assertTrue(self.appointment.is_confirmed)

    def test_owner_can_still_read_everything(self):
        for name in ("panel", "service_list", "professional_list", "plans"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

        agenda = self.client.get(reverse("panel"), {"date": future_date().isoformat()})
        self.assertContains(agenda, "Tu panel está en modo lectura.")
        self.assertNotContains(agenda, reverse("appointment_create"))
        self.assertNotContains(self.client.get(reverse("service_list")), "Agregar servicio")

    def test_public_page_stops_taking_bookings(self):
        page = self.client.get(reverse("booking_page", args=[self.business.slug]))
        response = self.client.post(
            reverse("book", args=[self.business.slug]),
            {
                "service": self.service.pk,
                "date": future_date().isoformat(),
                "start_at": local_dt(future_date(), 11).isoformat(),
                "customer_name": "Laura",
                "customer_phone": "11 5555 1234",
                "customer_email": "laura@example.com",
            },
        )

        self.assertContains(page, "todavía no está tomando reservas")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Appointment.objects.filter(business=self.business).count(), 1)

    def test_existing_appointments_are_honored(self):
        self.client.logout()
        token = self.appointment.manage_token

        reschedule = self.client.get(reverse("reschedule_appointment", args=[token]))
        cancel = self.client.post(reverse("cancel_appointment", args=[token]))

        self.assertContains(reschedule, "no está tomando reservas online")
        self.assertEqual(cancel.status_code, 302)
        self.appointment.refresh_from_db()
        self.assertFalse(self.appointment.is_confirmed)

    def test_reminders_still_go_out(self):
        start = (timezone.now() + timedelta(hours=23)).replace(second=0, microsecond=0)
        appointment = create_appointment(self.ana, self.service, start)
        appointment.reminder_due_at = start - timedelta(hours=24)
        appointment.save()

        self.assertEqual(send_due_reminders(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_nothing_is_deleted_when_the_trial_ends(self):
        call_command("run_billing_tasks", stdout=StringIO())

        self.assertTrue(Professional.objects.filter(pk=self.ana.pk).exists())
        self.assertTrue(Appointment.objects.filter(pk=self.appointment.pk).exists())
        self.assertTrue(Service.objects.filter(pk=self.service.pk).exists())


class ProfessionalLimitTests(TestCase):
    def setUp(self):
        self.business = create_business()
        self.ana = create_professional(self.business, name="Ana", ranges=())
        self.client.force_login(self.business.owner)

    def professional_data(self, name, is_active=True):
        data = {
            "name": name,
            "hours-TOTAL_FORMS": "0",
            "hours-INITIAL_FORMS": "0",
            "hours-MIN_NUM_FORMS": "0",
            "hours-MAX_NUM_FORMS": "1000",
        }
        if is_active:
            data["is_active"] = "on"
        return data

    def test_limit_blocks_creating_even_with_a_direct_request(self):
        set_active(self.business, "esencial")

        page = self.client.get(reverse("professional_create"))
        direct = self.client.post(reverse("professional_create"), self.professional_data("Bruno"))

        self.assertRedirects(page, reverse("professional_list"))
        self.assertRedirects(direct, reverse("professional_list"))
        self.assertFalse(Professional.objects.filter(name="Bruno").exists())

    def test_limit_blocks_reactivating(self):
        bruno = create_professional(self.business, name="Bruno", ranges=())
        bruno.is_active = False
        bruno.save()
        set_active(self.business, "esencial")

        response = self.client.post(
            reverse("professional_edit", args=[bruno.pk]), self.professional_data("Bruno")
        )

        self.assertContains(response, "Tu plan permite hasta 1 profesional activo")
        bruno.refresh_from_db()
        self.assertFalse(bruno.is_active)

    def test_editing_an_already_active_professional_is_allowed_at_the_limit(self):
        set_active(self.business, "esencial")

        response = self.client.post(
            reverse("professional_edit", args=[self.ana.pk]), self.professional_data("Ana María")
        )

        self.assertRedirects(response, reverse("professional_list"))

    def test_trial_allows_up_to_five(self):
        for name in ["B", "C", "D", "E"]:
            self.client.post(reverse("professional_create"), self.professional_data(name))
        blocked = self.client.post(reverse("professional_create"), self.professional_data("F"))

        self.assertEqual(Professional.objects.filter(business=self.business).count(), 5)
        self.assertRedirects(blocked, reverse("professional_list"))

    def test_cannot_choose_a_plan_below_the_active_professionals(self):
        create_professional(self.business, name="Bruno", ranges=())

        with self.assertRaises(PlanLimitExceeded):
            choose_plan(self.business.subscription, Plan.objects.get(code="esencial"))
        response = self.client.post(reverse("choose_plan", args=["esencial"]), follow=True)

        self.assertContains(response, "desactivá 1 para elegirlo")
        self.assertEqual(
            Subscription.objects.get(business=self.business).status, Subscription.TRIALING
        )

    def test_over_limit_after_a_change_keeps_everything_and_warns(self):
        create_professional(self.business, name="Bruno", ranges=())
        set_active(self.business, "esencial")

        response = self.client.get(reverse("panel"))

        self.assertContains(response, "Tenés 2 profesionales activos y tu plan permite 1")
        self.assertEqual(
            Professional.objects.filter(business=self.business, is_active=True).count(), 2
        )
        self.assertTrue(get_access(self.business).over_limit)


class IsolationTests(TestCase):
    def test_choosing_a_plan_only_touches_the_own_subscription(self):
        mine = create_business("a@example.com", "Mío")
        other = create_business("b@example.com", "Otro")
        self.client.force_login(mine.owner)

        self.client.post(reverse("choose_plan", args=["negocio"]))

        self.assertEqual(
            Subscription.objects.get(business=mine).status, Subscription.PENDING_PAYMENT
        )
        self.assertEqual(Subscription.objects.get(business=other).status, Subscription.TRIALING)

    def test_plans_page_requires_login(self):
        url = reverse("plans")

        self.assertRedirects(self.client.get(url), f"{reverse('login')}?next={url}")
        self.assertEqual(self.client.get(reverse("choose_plan", args=["negocio"])).status_code, 302)


class ActivationTests(TestCase):
    def test_activation_clears_the_choice_and_sets_the_plan(self):
        business = create_business()
        subscription = choose_plan(business.subscription, Plan.objects.get(code="negocio"))

        activate(subscription, subscription.selected_plan, None, "Pago confirmado")

        subscription.refresh_from_db()
        self.assertEqual(subscription.status, Subscription.ACTIVE)
        self.assertEqual(subscription.plan.code, "negocio")
        self.assertIsNone(subscription.selected_plan)
