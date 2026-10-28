"""Attendance (HU-34): the owner marks whether each customer came, once the appointment started."""

from datetime import timedelta

from django.core import mail
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from billing.tests.helpers import end_trial
from bookings.models import Appointment

from .helpers import (
    create_appointment,
    create_business,
    create_professional,
    create_service,
    future_date,
    local_dt,
)


class AttendanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business(name="Estética Luna")
        cls.ana = create_professional(cls.business, name="Ana")
        cls.bruno = create_professional(cls.business, name="Bruno")
        cls.service = create_service(cls.business, duration=50)
        cls.yesterday = timezone.localdate() - timedelta(days=1)

    def setUp(self):
        self.client.force_login(self.business.owner)
        self.past = create_appointment(self.ana, self.service, local_dt(self.yesterday, 10))

    def mark(self, appointment, attendance, **extra):
        return self.client.post(
            reverse("appointment_attendance", args=[appointment.pk]),
            {"attendance": attendance, **extra},
        )

    def refreshed(self, appointment):
        appointment.refresh_from_db()
        return appointment

    def agenda(self, date, **params):
        return self.client.get(reverse("panel"), {"date": date.isoformat(), **params})

    def test_mark_attended_then_no_show_then_clear(self):
        response = self.mark(self.past, Appointment.ATTENDED)
        self.assertRedirects(response, f"{reverse('panel')}?date={self.yesterday.isoformat()}")
        past = self.refreshed(self.past)
        self.assertEqual(past.attendance, Appointment.ATTENDED)
        self.assertIsNotNone(past.attendance_marked_at)

        self.mark(self.past, Appointment.NO_SHOW)
        self.assertEqual(self.refreshed(self.past).attendance, Appointment.NO_SHOW)

        self.mark(self.past, "")
        past = self.refreshed(self.past)
        self.assertEqual(past.attendance, Appointment.NOT_MARKED)
        self.assertIsNone(past.attendance_marked_at)
        self.assertEqual(len(mail.outbox), 0)

    def test_redirect_keeps_the_professional_filter(self):
        response = self.mark(self.past, Appointment.ATTENDED, professional=str(self.ana.pk))
        self.assertIn(f"professional={self.ana.pk}", response["Location"])

    def test_future_cancelled_or_unknown_values_are_ignored(self):
        future = create_appointment(self.ana, self.service, local_dt(future_date(), 10))
        cancelled = create_appointment(self.bruno, self.service, local_dt(self.yesterday, 10))
        cancelled.cancel()
        self.mark(future, Appointment.ATTENDED)
        self.mark(cancelled, Appointment.ATTENDED)
        self.mark(self.past, "maybe")
        self.assertEqual(self.refreshed(future).attendance, Appointment.NOT_MARKED)
        self.assertEqual(self.refreshed(cancelled).attendance, Appointment.NOT_MARKED)
        self.assertEqual(self.refreshed(self.past).attendance, Appointment.NOT_MARKED)

    def test_other_business_appointment_is_not_found(self):
        other = create_business("b@example.com", "Otro")
        theirs = create_appointment(
            create_professional(other, name="Zoe"),
            create_service(other),
            local_dt(self.yesterday, 10),
        )
        self.assertEqual(self.mark(theirs, Appointment.ATTENDED).status_code, 404)
        self.assertEqual(self.refreshed(theirs).attendance, Appointment.NOT_MARKED)

    def test_needs_post_and_an_editable_account(self):
        url = reverse("appointment_attendance", args=[self.past.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        end_trial(self.business)
        response = self.mark(self.past, Appointment.ATTENDED)
        self.assertRedirects(response, reverse("plans"), fetch_redirect_response=False)
        self.assertEqual(self.refreshed(self.past).attendance, Appointment.NOT_MARKED)

    def test_cancel_and_reschedule_clear_the_mark(self):
        self.past.mark_attendance(Appointment.NO_SHOW)
        self.past.move_to(local_dt(future_date(), 10))
        self.assertEqual(self.refreshed(self.past).attendance, Appointment.NOT_MARKED)

        other = create_appointment(self.bruno, self.service, local_dt(self.yesterday, 11))
        other.mark_attendance(Appointment.ATTENDED)
        other.cancel()
        self.assertEqual(self.refreshed(other).attendance, Appointment.NOT_MARKED)

    def test_database_rejects_a_mark_on_a_cancelled_appointment(self):
        self.past.cancel()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Appointment.objects.filter(pk=self.past.pk).update(attendance=Appointment.ATTENDED)

    def test_agenda_shows_buttons_only_on_started_appointments_and_the_summary(self):
        create_appointment(self.bruno, self.service, local_dt(self.yesterday, 10))
        third = create_appointment(self.ana, self.service, local_dt(self.yesterday, 15))
        self.past.mark_attendance(Appointment.ATTENDED)
        third.mark_attendance(Appointment.NO_SHOW)

        response = self.agenda(self.yesterday)
        self.assertContains(response, reverse("appointment_attendance", args=[self.past.pk]))
        self.assertContains(response, 'aria-pressed="true"', count=2)
        self.assertContains(response, "<strong>1</strong> asistió")
        self.assertContains(response, "<strong>1</strong> no asistió")
        self.assertContains(response, "<strong>1</strong> sin marcar")

        future = future_date()
        create_appointment(self.ana, self.service, local_dt(future, 10))
        response = self.agenda(future)
        self.assertNotContains(response, "/attendance/")  # no attendance form for the future
        self.assertNotContains(response, "Asistencia:")

    def test_read_only_agenda_shows_the_mark_without_buttons(self):
        self.past.mark_attendance(Appointment.ATTENDED)
        end_trial(self.business)
        response = self.agenda(self.yesterday)
        self.assertContains(response, '<span class="badge">Asistió</span>')
        self.assertNotContains(response, reverse("appointment_attendance", args=[self.past.pk]))
