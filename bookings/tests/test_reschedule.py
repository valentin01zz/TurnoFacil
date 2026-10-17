from datetime import timedelta
from unittest import mock

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.availability import available_slots
from bookings.models import Appointment
from bookings.views import TAKEN_MESSAGE

from .helpers import (
    create_appointment,
    create_business,
    create_professional,
    create_service,
    future_date,
    local_dt,
)


class RescheduleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business(name="Estética Luna")
        cls.ana = create_professional(cls.business, name="Ana")
        cls.service = create_service(cls.business, name="Limpieza facial", duration=50)
        cls.date = future_date()
        cls.new_date = future_date(days=9)

    def setUp(self):
        self.appointment = create_appointment(self.ana, self.service, local_dt(self.date, 10, 0))
        self.appointment.reminder_due_at = self.appointment.start_at - timedelta(hours=24)
        self.appointment.reminder_sent_at = timezone.now()
        self.appointment.save()

    def url(self, appointment=None):
        appointment = appointment or self.appointment
        return reverse("reschedule_appointment", args=[appointment.manage_token])

    def detail_url(self, appointment=None):
        appointment = appointment or self.appointment
        return reverse("appointment_detail", args=[appointment.manage_token])

    def move(self, start_at, appointment=None):
        return self.client.post(
            self.url(appointment),
            {"date": timezone.localdate(start_at).isoformat(), "start_at": start_at.isoformat()},
        )

    def starting_in(self, hours):
        start_at = (timezone.now() + timedelta(hours=hours)).replace(microsecond=0)
        return create_appointment(self.ana, self.service, start_at)

    def test_detail_offers_rescheduling(self):
        response = self.client.get(self.detail_url())

        self.assertContains(response, self.url())

    def test_shows_free_times_for_a_new_day(self):
        create_appointment(self.ana, self.service, local_dt(self.new_date, 9, 0))

        response = self.client.get(self.url(), {"date": self.new_date.isoformat()})

        self.assertContains(response, "Horarios disponibles")
        self.assertNotContains(response, local_dt(self.new_date, 9, 0).isoformat())
        self.assertContains(response, local_dt(self.new_date, 11, 0).isoformat())

    def test_same_day_offers_overlapping_times_but_not_the_current_one(self):
        response = self.client.get(self.url(), {"date": self.date.isoformat()})

        self.assertNotContains(response, f'value="{local_dt(self.date, 10, 0).isoformat()}"')
        self.assertContains(response, local_dt(self.date, 10, 30).isoformat())

    def test_moving_updates_the_appointment_frees_the_old_time_and_emails(self):
        new_start = local_dt(self.new_date, 11, 0)

        response = self.move(new_start)

        self.assertRedirects(response, self.detail_url())
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.start_at, new_start)
        self.assertEqual(self.appointment.end_at, local_dt(self.new_date, 11, 50))
        self.assertTrue(self.appointment.is_confirmed)
        self.assertEqual(Appointment.objects.count(), 1)
        free = available_slots(self.ana, self.service, self.date)
        self.assertIn(local_dt(self.date, 10, 0), free)

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.subject, "Turno reprogramado en Estética Luna")
        self.assertIn("11:00", message.body)
        self.assertIn(f"{self.new_date.day} de", message.body)
        self.assertIn(f"/t/{self.appointment.manage_token}/", message.body)

    def test_reminder_follows_the_new_date(self):
        new_start = local_dt(self.new_date, 11, 0)

        self.move(new_start)

        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.reminder_due_at, new_start - timedelta(hours=24))
        self.assertIsNone(self.appointment.reminder_sent_at)

    def test_moving_within_the_current_time_range_works(self):
        response = self.move(local_dt(self.date, 10, 30))

        self.assertRedirects(response, self.detail_url())
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.start_at, local_dt(self.date, 10, 30))

    def test_taken_time_is_rejected(self):
        create_appointment(self.ana, self.service, local_dt(self.new_date, 9, 0))

        response = self.move(local_dt(self.new_date, 9, 0))

        self.assertContains(response, "Ese horario ya no está disponible.")
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.start_at, local_dt(self.date, 10, 0))
        self.assertEqual(len(mail.outbox), 0)

    def test_simultaneous_change_keeps_the_original_time(self):
        target = local_dt(self.new_date, 9, 0)
        create_appointment(self.ana, self.service, target)

        with mock.patch("bookings.views.available_slots", return_value=[target]):
            response = self.move(target)

        self.assertContains(response, TAKEN_MESSAGE)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.start_at, local_dt(self.date, 10, 0))

    def test_less_than_two_hours_before_cannot_reschedule(self):
        soon = self.starting_in(hours=1)
        original = soon.start_at

        page = self.client.get(self.url(soon))
        response = self.move(local_dt(self.new_date, 11, 0), appointment=soon)

        self.assertContains(page, "Faltan menos de 2 horas")
        self.assertNotContains(page, "Elegí el nuevo horario")
        self.assertContains(response, "Faltan menos de 2 horas")
        soon.refresh_from_db()
        self.assertEqual(soon.start_at, original)

    def test_cancelled_appointment_cannot_be_rescheduled(self):
        self.appointment.cancel()

        response = self.move(local_dt(self.new_date, 11, 0))

        self.assertContains(response, "Turno cancelado")
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.start_at, local_dt(self.date, 10, 0))

    def test_past_appointment_cannot_be_rescheduled(self):
        past = create_appointment(
            self.ana, self.service, local_dt(timezone.localdate() - timedelta(days=1), 10, 0)
        )

        response = self.move(local_dt(self.new_date, 11, 0), appointment=past)

        self.assertContains(response, "Este turno ya pasó.")
        past.refresh_from_db()
        self.assertEqual(past.start_at.date(), (timezone.localdate() - timedelta(days=1)))

    def test_date_outside_the_window_is_rejected(self):
        far = timezone.localdate() + timedelta(days=61)

        response = self.client.post(
            self.url(), {"date": far.isoformat(), "start_at": local_dt(far, 10, 0).isoformat()}
        )

        self.assertEqual(response.status_code, 400)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.start_at, local_dt(self.date, 10, 0))

    def test_unknown_token_returns_not_found(self):
        response = self.client.get(reverse("reschedule_appointment", args=["no-existe"]))

        self.assertContains(response, "Turno no encontrado", status_code=404)


class RescheduleProfessionalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business(name="Estética Luna")
        cls.ana = create_professional(cls.business, name="Ana")
        cls.bruno = create_professional(cls.business, name="Bruno")
        cls.service = create_service(cls.business, name="Limpieza facial", duration=50)
        cls.date = future_date()

    def setUp(self):
        self.appointment = create_appointment(self.ana, self.service, local_dt(self.date, 10, 0))
        self.url = reverse("reschedule_appointment", args=[self.appointment.manage_token])

    def move(self, professional, start_at):
        return self.client.post(
            self.url,
            {
                "professional": professional.pk,
                "date": self.date.isoformat(),
                "start_at": start_at.isoformat(),
            },
        )

    def test_page_offers_the_professionals_with_the_current_one_selected(self):
        response = self.client.get(self.url)

        self.assertContains(response, "Bruno")
        self.assertContains(response, f'<option value="{self.ana.pk}" selected>Ana</option>')

    def test_same_time_with_another_professional_is_offered(self):
        response = self.client.get(
            self.url, {"professional": self.bruno.pk, "date": self.date.isoformat()}
        )

        self.assertContains(response, f'value="{local_dt(self.date, 10, 0).isoformat()}"')

    def test_times_taken_by_the_other_professional_are_not_offered(self):
        create_appointment(self.bruno, self.service, local_dt(self.date, 11, 0))

        response = self.client.get(
            self.url, {"professional": self.bruno.pk, "date": self.date.isoformat()}
        )

        self.assertNotContains(response, local_dt(self.date, 11, 0).isoformat())

    def test_moving_to_another_professional(self):
        response = self.move(self.bruno, local_dt(self.date, 10, 0))

        self.assertEqual(response.status_code, 302)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.professional, self.bruno)
        self.assertEqual(self.appointment.start_at, local_dt(self.date, 10, 0))
        self.assertIn(
            local_dt(self.date, 10, 0), available_slots(self.ana, self.service, self.date)
        )
        self.assertIn("Profesional: Bruno", mail.outbox[0].body)

    def test_inactive_or_foreign_professionals_are_rejected(self):
        inactive = create_professional(self.business, name="Ciro")
        inactive.is_active = False
        inactive.save()
        foreign = create_professional(create_business("b@example.com", "Taller Sur"), "Carlos")

        for professional in [inactive, foreign]:
            response = self.move(professional, local_dt(self.date, 11, 0))
            self.assertEqual(response.status_code, 400, professional.name)

        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.professional, self.ana)
