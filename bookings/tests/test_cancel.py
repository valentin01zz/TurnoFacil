from datetime import timedelta

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


class CancelAppointmentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business()
        cls.ana = create_professional(cls.business, name="Ana")
        cls.service = create_service(cls.business, duration=50)
        cls.date = future_date()

    def setUp(self):
        self.appointment = create_appointment(self.ana, self.service, local_dt(self.date, 10, 0))
        self.appointment.reminder_due_at = self.appointment.start_at - timedelta(hours=24)
        self.appointment.save()

    def cancel_url(self, appointment=None):
        return reverse("cancel_appointment", args=[(appointment or self.appointment).manage_token])

    def detail_url(self, appointment=None):
        return reverse("appointment_detail", args=[(appointment or self.appointment).manage_token])

    def starting_in(self, hours):
        start_at = timezone.now() + timedelta(hours=hours)
        return create_appointment(self.ana, self.service, start_at.replace(microsecond=0))

    def test_detail_offers_cancellation(self):
        response = self.client.get(self.detail_url())

        self.assertContains(response, self.cancel_url())

    def test_cancel_asks_for_confirmation_first(self):
        response = self.client.get(self.cancel_url())

        self.assertContains(response, "¿Cancelar este turno?")
        self.appointment.refresh_from_db()
        self.assertTrue(self.appointment.is_confirmed)

    def test_confirmed_cancellation_frees_the_slot(self):
        response = self.client.post(self.cancel_url())

        self.assertRedirects(response, self.detail_url())
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.CANCELLED)
        self.assertIsNotNone(self.appointment.cancelled_at)
        self.assertIn(
            local_dt(self.date, 10, 0), available_slots(self.ana, self.service, self.date)
        )
        self.assertContains(self.client.get(self.detail_url()), "Turno cancelado")

    def test_cancelled_appointment_will_not_get_a_reminder(self):
        self.client.post(self.cancel_url())

        self.appointment.refresh_from_db()
        self.assertIsNone(self.appointment.reminder_due_at)

    def test_cancelling_twice_says_it_was_already_cancelled(self):
        self.client.post(self.cancel_url())

        response = self.client.post(self.cancel_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Este turno ya estaba cancelado.")

    def test_less_than_two_hours_before_cannot_cancel(self):
        soon = self.starting_in(hours=1)

        detail = self.client.get(self.detail_url(soon))
        response = self.client.post(self.cancel_url(soon))

        self.assertNotContains(detail, self.cancel_url(soon))
        self.assertContains(detail, "Faltan menos de 2 horas")
        self.assertContains(response, "Faltan menos de 2 horas")
        soon.refresh_from_db()
        self.assertTrue(soon.is_confirmed)

    def test_more_than_two_hours_before_can_cancel(self):
        later = self.starting_in(hours=3)

        self.client.post(self.cancel_url(later))

        later.refresh_from_db()
        self.assertFalse(later.is_confirmed)

    def test_past_appointment_cannot_be_cancelled(self):
        past = create_appointment(
            self.ana, self.service, local_dt(timezone.localdate() - timedelta(days=1), 10, 0)
        )

        response = self.client.post(self.cancel_url(past))

        self.assertContains(response, "Este turno ya pasó.")
        past.refresh_from_db()
        self.assertTrue(past.is_confirmed)

    def test_cancel_page_for_a_cancelled_appointment_shows_the_detail(self):
        self.client.post(self.cancel_url())

        response = self.client.get(self.cancel_url())

        self.assertContains(response, "Turno cancelado")
        self.assertNotContains(response, "¿Cancelar este turno?")

    def test_unknown_token_cannot_cancel(self):
        response = self.client.post(reverse("cancel_appointment", args=["no-existe"]))

        self.assertContains(response, "Turno no encontrado", status_code=404)
        self.appointment.refresh_from_db()
        self.assertTrue(self.appointment.is_confirmed)
