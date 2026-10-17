from datetime import timedelta
from unittest import mock

from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Appointment
from bookings.views import TAKEN_MESSAGE
from bookings.views import create_appointment as create_from_form

from .helpers import (
    create_appointment,
    create_business,
    create_professional,
    create_service,
    future_date,
    local_dt,
)


class BookingFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business()
        cls.ana = create_professional(cls.business, name="Ana")
        cls.bruno = create_professional(cls.business, name="Bruno")
        cls.service = create_service(cls.business, duration=50)
        cls.date = future_date()

    def page_url(self):
        return reverse("booking_page", args=[self.business.slug])

    def book_url(self):
        return reverse("book", args=[self.business.slug])

    def booking_data(self, start_at=None, **overrides):
        start_at = start_at or local_dt(self.date, 9, 0)
        data = {
            "service": self.service.pk,
            "professional": self.ana.pk,
            "date": self.date.isoformat(),
            "start_at": start_at.isoformat(),
            "customer_name": "Laura Gómez",
            "customer_phone": "+54 11 5555-1234",
            "customer_email": "laura@example.com",
            "website": "",
        }
        data.update(overrides)
        return data

    def test_page_offers_services_and_professionals(self):
        response = self.client.get(self.page_url())

        self.assertContains(response, "Limpieza facial")
        self.assertContains(response, "Ana")
        self.assertContains(response, "Bruno")
        self.assertNotContains(response, "Horarios disponibles")

    def test_page_shows_free_times_for_the_chosen_professional(self):
        create_appointment(self.ana, self.service, local_dt(self.date, 9, 0))

        response = self.client.get(
            self.page_url(),
            {"service": self.service.pk, "professional": self.ana.pk, "date": self.date},
        )

        self.assertContains(response, "Horarios disponibles")
        self.assertNotContains(response, local_dt(self.date, 9, 0).isoformat())
        self.assertContains(response, local_dt(self.date, 10, 0).isoformat())
        self.assertContains(response, "Confirmar turno")

    def test_valid_booking_creates_the_appointment(self):
        response = self.client.post(self.book_url(), self.booking_data())

        appointment = Appointment.objects.get()
        self.assertRedirects(
            response, reverse("appointment_detail", args=[appointment.manage_token])
        )
        self.assertEqual(appointment.business, self.business)
        self.assertEqual(appointment.professional, self.ana)
        self.assertEqual(appointment.service, self.service)
        self.assertEqual(appointment.start_at, local_dt(self.date, 9, 0))
        self.assertEqual(appointment.end_at, local_dt(self.date, 9, 50))
        self.assertEqual(appointment.status, Appointment.CONFIRMED)
        self.assertEqual(appointment.source, Appointment.ONLINE)
        self.assertEqual(appointment.customer_email, "laura@example.com")
        self.assertGreaterEqual(len(appointment.manage_token), 40)

        detail = self.client.get(response.url)
        self.assertContains(detail, "Turno confirmado")
        self.assertContains(detail, "Limpieza facial con Ana")
        self.assertContains(detail, "09:00")

    def test_booked_time_is_no_longer_offered(self):
        self.client.post(self.book_url(), self.booking_data())

        response = self.client.get(
            self.page_url(),
            {"service": self.service.pk, "professional": self.ana.pk, "date": self.date},
        )

        self.assertNotContains(response, local_dt(self.date, 9, 0).isoformat())

    def test_simultaneous_booking_keeps_only_the_first(self):
        start_at = local_dt(self.date, 9, 0)
        create_appointment(self.ana, self.service, start_at)

        # Simulate the race: availability was computed before the other booking was saved.
        with mock.patch("bookings.views.available_slots", return_value=[start_at]):
            response = self.client.post(self.book_url(), self.booking_data(start_at))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, TAKEN_MESSAGE)
        self.assertEqual(Appointment.objects.count(), 1)

    def test_time_not_offered_is_rejected(self):
        for start_at in [local_dt(self.date, 8, 0), local_dt(self.date, 9, 10)]:
            response = self.client.post(self.book_url(), self.booking_data(start_at))
            self.assertContains(response, "Ese horario ya no está disponible.")

        self.assertFalse(Appointment.objects.exists())

    def test_missing_or_invalid_customer_data_is_rejected(self):
        cases = {
            "customer_name": "",
            "customer_phone": "",
            "customer_email": "",
        }
        for field, value in cases.items():
            response = self.client.post(self.book_url(), self.booking_data(**{field: value}))
            self.assertTrue(response.context["booking"].errors[field], field)

        bad_values = {"customer_email": "no-es-un-email", "customer_phone": "llamame"}
        for field, value in bad_values.items():
            response = self.client.post(self.book_url(), self.booking_data(**{field: value}))
            self.assertTrue(response.context["booking"].errors[field], field)

        self.assertFalse(Appointment.objects.exists())

    def test_past_or_far_dates_are_rejected(self):
        today = timezone.localdate()
        for date in [today - timedelta(days=1), today + timedelta(days=61)]:
            response = self.client.post(
                self.book_url(),
                self.booking_data(local_dt(date, 9, 0), date=date.isoformat()),
            )
            self.assertEqual(response.status_code, 400, date)

        self.assertFalse(Appointment.objects.exists())

    def test_honeypot_blocks_the_booking(self):
        response = self.client.post(self.book_url(), self.booking_data(website="spam"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Appointment.objects.exists())

    def test_other_business_or_inactive_choices_are_rejected(self):
        other = create_business("b@example.com", "Taller Sur")
        foreign_professional = create_professional(other, name="Carlos")
        foreign_service = create_service(other, name="Cambio de aceite")
        inactive = create_service(self.business, name="Viejo")
        inactive.is_active = False
        inactive.save()

        for overrides in [
            {"professional": foreign_professional.pk},
            {"service": foreign_service.pk},
            {"service": inactive.pk},
        ]:
            response = self.client.post(self.book_url(), self.booking_data(**overrides))
            self.assertEqual(response.status_code, 400, overrides)

        self.assertFalse(Appointment.objects.exists())

    def test_booking_requires_post(self):
        response = self.client.get(self.book_url())

        self.assertEqual(response.status_code, 405)

    def test_unknown_token_returns_404(self):
        response = self.client.get(reverse("appointment_detail", args=["no-existe"]))

        self.assertEqual(response.status_code, 404)


class SingleProfessionalBookingTests(TestCase):
    def test_booking_without_choosing_a_professional(self):
        business = create_business()
        ana = create_professional(business, name="Ana")
        service = create_service(business)
        date = future_date()

        page = self.client.get(
            reverse("booking_page", args=[business.slug]), {"service": service.pk, "date": date}
        )
        response = self.client.post(
            reverse("book", args=[business.slug]),
            {
                "service": service.pk,
                "professional": "",
                "date": date.isoformat(),
                "start_at": local_dt(date, 9, 0).isoformat(),
                "customer_name": "Laura Gómez",
                "customer_phone": "11 5555 1234",
                "customer_email": "laura@example.com",
            },
        )

        self.assertContains(page, "Horarios disponibles")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Appointment.objects.get().professional, ana)


class AppointmentRulesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business()
        cls.professional = create_professional(cls.business)
        cls.service = create_service(cls.business, duration=50)
        cls.date = future_date()

    def form_data(self, start_at):
        return {
            "start_at": start_at,
            "customer_name": "Laura",
            "customer_phone": "11 5555 1234",
            "customer_email": "laura@example.com",
        }

    def test_reminder_is_due_24_hours_before(self):
        start_at = timezone.now() + timedelta(days=3)

        appointment = create_from_form(
            self.business, self.professional, self.service, self.form_data(start_at)
        )

        self.assertEqual(appointment.reminder_due_at, start_at - timedelta(hours=24))

    def test_no_reminder_when_booked_less_than_24_hours_before(self):
        start_at = timezone.now() + timedelta(hours=2)

        appointment = create_from_form(
            self.business, self.professional, self.service, self.form_data(start_at)
        )

        self.assertIsNone(appointment.reminder_due_at)

    def test_database_rejects_overlapping_confirmed_appointments(self):
        create_appointment(self.professional, self.service, local_dt(self.date, 10, 0))

        with self.assertRaises(IntegrityError):
            create_appointment(self.professional, self.service, local_dt(self.date, 10, 30))

    def test_database_allows_back_to_back_and_cancelled_overlaps(self):
        create_appointment(self.professional, self.service, local_dt(self.date, 10, 0))

        create_appointment(self.professional, self.service, local_dt(self.date, 10, 50))
        create_appointment(
            self.professional,
            self.service,
            local_dt(self.date, 10, 0),
            status=Appointment.CANCELLED,
        )

        self.assertEqual(Appointment.objects.count(), 3)

    def test_editing_a_service_does_not_change_booked_appointments(self):
        appointment = create_appointment(
            self.professional, self.service, local_dt(self.date, 10, 0)
        )

        self.service.duration_minutes = 90
        self.service.save()

        appointment.refresh_from_db()
        self.assertEqual(appointment.end_at, local_dt(self.date, 10, 50))
