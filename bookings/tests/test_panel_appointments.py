from datetime import timedelta

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.availability import available_slots
from bookings.models import Appointment

from .helpers import (
    create_appointment,
    create_business,
    create_professional,
    create_service,
    future_date,
    local_dt,
)


class PanelAppointmentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business(name="Estética Luna")
        cls.ana = create_professional(cls.business, name="Ana")
        cls.bruno = create_professional(cls.business, name="Bruno")
        cls.service = create_service(cls.business, name="Limpieza facial", duration=50)
        cls.date = future_date()

        cls.other = create_business("b@example.com", "Taller Sur")
        carlos = create_professional(cls.other, name="Carlos")
        cls.foreign = create_appointment(
            carlos, create_service(cls.other, name="Aceite"), local_dt(cls.date, 10, 0)
        )

    def setUp(self):
        self.client.force_login(self.business.owner)

    def agenda(self, date=None):
        return self.client.get(reverse("panel"), {"date": (date or self.date).isoformat()})

    def new_data(self, **overrides):
        data = {
            "customer_name": "Juan Pérez",
            "customer_phone": "11 4444 5555",
            "customer_email": "",
            "service": self.service.pk,
            "professional": self.ana.pk,
            "date": self.date.isoformat(),
            "time": "10:00",
        }
        data.update(overrides)
        return data

    def create(self, **overrides):
        return self.client.post(reverse("appointment_create"), self.new_data(**overrides))

    # --- Create ---

    def test_pages_require_login(self):
        self.client.logout()
        appointment = create_appointment(self.ana, self.service, local_dt(self.date, 9, 0))

        for url in [
            reverse("appointment_create"),
            reverse("appointment_reschedule", args=[appointment.pk]),
            reverse("appointment_cancel", args=[appointment.pk]),
        ]:
            response = self.client.get(url)
            self.assertRedirects(response, f"{reverse('login')}?next={url}")

    def test_manual_appointment_appears_in_agenda_and_blocks_the_slot(self):
        response = self.create()

        appointment = Appointment.objects.get(business=self.business)
        self.assertRedirects(response, f"{reverse('panel')}?date={self.date.isoformat()}")
        self.assertEqual(appointment.source, Appointment.MANUAL)
        self.assertEqual(appointment.start_at, local_dt(self.date, 10, 0))
        self.assertEqual(appointment.end_at, local_dt(self.date, 10, 50))
        self.assertEqual(appointment.customer_email, "")
        self.assertIsNone(appointment.reminder_due_at)
        self.assertContains(self.agenda(), "Juan Pérez")
        self.assertContains(self.agenda(), "Cargado a mano")
        self.assertNotIn(
            local_dt(self.date, 10, 0), available_slots(self.ana, self.service, self.date)
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_manual_appointment_with_email_sends_confirmation(self):
        self.create(customer_email="juan@example.com")

        appointment = Appointment.objects.get(business=self.business)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["juan@example.com"])
        self.assertIn(f"/t/{appointment.manage_token}/", mail.outbox[0].body)
        self.assertEqual(appointment.reminder_due_at, appointment.start_at - timedelta(hours=24))

    def test_owner_can_book_outside_working_hours(self):
        response = self.create(time="20:15")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            Appointment.objects.get(business=self.business).start_at,
            local_dt(self.date, 20, 15),
        )

    def test_overlapping_manual_appointment_is_rejected(self):
        create_appointment(self.ana, self.service, local_dt(self.date, 10, 0))

        response = self.create(time="10:30")

        self.assertContains(response, "Ese horario se superpone con otro turno de Ana.")
        self.assertEqual(Appointment.objects.filter(business=self.business).count(), 1)

    def test_same_time_with_another_professional_is_allowed(self):
        create_appointment(self.ana, self.service, local_dt(self.date, 10, 0))

        response = self.create(professional=self.bruno.pk)

        self.assertEqual(response.status_code, 302)

    def test_invalid_manual_data_is_rejected(self):
        past = timezone.localdate() - timedelta(days=1)
        cases = [
            {"customer_name": ""},
            {"customer_phone": "llamame"},
            {"customer_email": "no-es-email"},
            {"date": past.isoformat()},
            {"professional": self.foreign.professional.pk},
            {"service": self.foreign.service.pk},
        ]
        for overrides in cases:
            response = self.create(**overrides)
            self.assertEqual(response.status_code, 200, overrides)
            self.assertTrue(response.context["form"].errors, overrides)

        self.assertFalse(Appointment.objects.filter(business=self.business).exists())

    def test_create_form_starts_on_the_agenda_day(self):
        response = self.client.get(reverse("appointment_create"), {"date": self.date.isoformat()})

        self.assertContains(response, f'value="{self.date.isoformat()}"')

    # --- Reschedule ---

    def test_reschedule_moves_the_appointment_and_emails_the_customer(self):
        appointment = create_appointment(self.ana, self.service, local_dt(self.date, 10, 0))

        response = self.client.post(
            reverse("appointment_reschedule", args=[appointment.pk]),
            {"professional": self.bruno.pk, "date": self.date.isoformat(), "time": "15:00"},
        )

        self.assertEqual(response.status_code, 302)
        appointment.refresh_from_db()
        self.assertEqual(appointment.professional, self.bruno)
        self.assertEqual(appointment.start_at, local_dt(self.date, 15, 0))
        self.assertIn(
            local_dt(self.date, 10, 0), available_slots(self.ana, self.service, self.date)
        )
        self.assertEqual(mail.outbox[0].subject, "Turno reprogramado en Estética Luna")
        self.assertIn("15:00", mail.outbox[0].body)

    def test_reschedule_has_no_two_hour_limit(self):
        soon = create_appointment(
            self.ana, self.service, (timezone.now() + timedelta(hours=1)).replace(microsecond=0)
        )

        response = self.client.post(
            reverse("appointment_reschedule", args=[soon.pk]),
            {"professional": self.ana.pk, "date": self.date.isoformat(), "time": "11:00"},
        )

        self.assertEqual(response.status_code, 302)
        soon.refresh_from_db()
        self.assertEqual(soon.start_at, local_dt(self.date, 11, 0))

    def test_reschedule_onto_another_appointment_is_rejected(self):
        moving = create_appointment(self.ana, self.service, local_dt(self.date, 9, 0))
        create_appointment(self.ana, self.service, local_dt(self.date, 11, 0))

        response = self.client.post(
            reverse("appointment_reschedule", args=[moving.pk]),
            {"professional": self.ana.pk, "date": self.date.isoformat(), "time": "11:30"},
        )

        self.assertContains(response, "Ese horario se superpone con otro turno de Ana.")
        self.assertContains(response, "a las 09:00")
        moving.refresh_from_db()
        self.assertEqual(moving.start_at, local_dt(self.date, 9, 0))
        self.assertEqual(len(mail.outbox), 0)

    def test_reschedule_without_email_sends_nothing(self):
        appointment = create_appointment(self.ana, self.service, local_dt(self.date, 10, 0))
        appointment.customer_email = ""
        appointment.save()

        self.client.post(
            reverse("appointment_reschedule", args=[appointment.pk]),
            {"professional": self.ana.pk, "date": self.date.isoformat(), "time": "12:00"},
        )

        appointment.refresh_from_db()
        self.assertEqual(appointment.start_at, local_dt(self.date, 12, 0))
        self.assertEqual(len(mail.outbox), 0)

    # --- Cancel ---

    def test_cancel_asks_for_confirmation_then_frees_the_slot_and_emails(self):
        appointment = create_appointment(self.ana, self.service, local_dt(self.date, 10, 0))
        url = reverse("appointment_cancel", args=[appointment.pk])

        confirm = self.client.get(url)
        response = self.client.post(url)

        self.assertContains(confirm, "¿Cancelar este turno?")
        self.assertEqual(response.status_code, 302)
        appointment.refresh_from_db()
        self.assertFalse(appointment.is_confirmed)
        self.assertNotContains(self.agenda(), appointment.customer_name)
        self.assertIn(
            local_dt(self.date, 10, 0), available_slots(self.ana, self.service, self.date)
        )
        self.assertEqual(mail.outbox[0].subject, "Turno cancelado en Estética Luna")

    def test_cancel_has_no_two_hour_limit(self):
        soon = create_appointment(
            self.ana, self.service, (timezone.now() + timedelta(hours=1)).replace(microsecond=0)
        )

        self.client.post(reverse("appointment_cancel", args=[soon.pk]))

        soon.refresh_from_db()
        self.assertFalse(soon.is_confirmed)

    def test_cancelling_twice_sends_one_email(self):
        appointment = create_appointment(self.ana, self.service, local_dt(self.date, 10, 0))
        url = reverse("appointment_cancel", args=[appointment.pk])

        self.client.post(url)
        response = self.client.post(url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

    # --- Isolation ---

    def test_other_business_appointments_return_404(self):
        for name in ["appointment_reschedule", "appointment_cancel"]:
            url = reverse(name, args=[self.foreign.pk])
            self.assertEqual(self.client.get(url).status_code, 404, name)
            self.assertEqual(self.client.post(url, {}).status_code, 404, name)

        self.foreign.refresh_from_db()
        self.assertTrue(self.foreign.is_confirmed)
        self.assertEqual(self.foreign.start_at, local_dt(self.date, 10, 0))

    def test_agenda_links_to_actions(self):
        appointment = create_appointment(self.ana, self.service, local_dt(self.date, 10, 0))

        response = self.agenda()

        self.assertContains(response, reverse("appointment_reschedule", args=[appointment.pk]))
        self.assertContains(response, reverse("appointment_cancel", args=[appointment.pk]))
        self.assertContains(response, f"{reverse('appointment_create')}?date={self.date}")
