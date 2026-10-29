"""Owner notices (HU-14): an email to the business when a customer books, reschedules or cancels."""

from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from bookings.models import Appointment
from businesses.models import TimeOff

from .helpers import (
    create_appointment,
    create_business,
    create_professional,
    create_service,
    future_date,
    local_dt,
    sent_to,
)

OWNER = "a@example.com"


class OwnerNotificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business(OWNER, name="Estética Luna")
        cls.ana = create_professional(cls.business, name="Ana")
        cls.bruno = create_professional(cls.business, name="Bruno")
        cls.service = create_service(cls.business, name="Limpieza facial", duration=50)
        cls.date = future_date()
        cls.new_date = future_date(days=9)

    def book(self, hour=10, email="laura@example.com"):
        return self.client.post(
            reverse("book", args=[self.business.slug]),
            {
                "service": self.service.pk,
                "professional": self.ana.pk,
                "date": self.date.isoformat(),
                "start_at": local_dt(self.date, hour).isoformat(),
                "customer_name": "Laura Gómez",
                "customer_phone": "11 5555 1234",
                "customer_email": email,
            },
        )

    def owner_mail(self):
        return sent_to(OWNER)

    def test_online_booking_notifies_the_owner(self):
        self.book()
        [message] = self.owner_mail()
        self.assertEqual(message.subject, "Nueva reserva: Laura Gómez")
        for text in [
            "Laura Gómez",
            "11 5555 1234",
            "laura@example.com",
            "Limpieza facial",
            "Ana",
            "10:00",
            f"{self.date.day} de",
            f"/panel/?date={self.date.isoformat()}",
        ]:
            self.assertIn(text, message.body)
        self.assertNotIn("/t/", message.body)  # never the customer's private link

    def test_customer_reschedule_shows_before_and_after(self):
        appointment = create_appointment(self.ana, self.service, local_dt(self.date, 10))
        new_start = local_dt(self.new_date, 11)
        self.client.post(
            reverse("reschedule_appointment", args=[appointment.manage_token]),
            {
                "professional": self.bruno.pk,
                "date": self.new_date.isoformat(),
                "start_at": new_start.isoformat(),
            },
        )
        [message] = self.owner_mail()
        self.assertEqual(message.subject, "Turno reprogramado: Cliente")
        self.assertRegex(message.body, r"Antes: .* a las 10:00, con Ana")
        self.assertRegex(message.body, r"Ahora: .* a las 11:00, con Bruno")
        self.assertIn(f"/panel/?date={self.new_date.isoformat()}", message.body)

    def test_same_professional_reschedule_names_them_once(self):
        appointment = create_appointment(self.ana, self.service, local_dt(self.date, 10))
        self.client.post(
            reverse("reschedule_appointment", args=[appointment.manage_token]),
            {
                "professional": self.ana.pk,
                "date": self.new_date.isoformat(),
                "start_at": local_dt(self.new_date, 11).isoformat(),
            },
        )
        [message] = self.owner_mail()
        self.assertIn("Profesional: Ana", message.body)
        self.assertNotIn(", con", message.body)

    def test_customer_cancel_notifies_the_owner(self):
        appointment = create_appointment(self.ana, self.service, local_dt(self.date, 10))
        self.client.post(reverse("cancel_appointment", args=[appointment.manage_token]))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.CANCELLED)
        [message] = self.owner_mail()
        self.assertEqual(message.subject, "Turno cancelado: Cliente")
        self.assertIn("10:00", message.body)

    def test_repeated_cancel_notifies_only_once(self):
        appointment = create_appointment(self.ana, self.service, local_dt(self.date, 10))
        url = reverse("cancel_appointment", args=[appointment.manage_token])
        self.client.post(url)
        self.client.post(url)
        self.assertEqual(len(self.owner_mail()), 1)

    def test_owner_actions_in_the_panel_send_no_owner_notice(self):
        self.client.force_login(self.business.owner)
        self.client.post(
            reverse("appointment_create"),
            {
                "customer_name": "Marta",
                "customer_phone": "11 4444 4444",
                "customer_email": "marta@example.com",
                "service": self.service.pk,
                "professional": self.ana.pk,
                "date": self.date.isoformat(),
                "time": "15:00",
            },
        )
        appointment = Appointment.objects.get()
        self.client.post(
            reverse("appointment_reschedule", args=[appointment.pk]),
            {"professional": self.ana.pk, "date": self.date.isoformat(), "time": "16:00"},
        )
        self.client.post(reverse("appointment_cancel", args=[appointment.pk]))
        other = create_appointment(self.ana, self.service, local_dt(self.new_date, 10))
        time_off = TimeOff.objects.create(
            business=self.business,
            start_at=local_dt(self.new_date, 0),
            end_at=local_dt(self.new_date, 23),
        )
        self.client.post(
            reverse("time_off_appointments", args=[time_off.pk]), {"appointments": [other.pk]}
        )
        other.refresh_from_db()
        self.assertEqual(other.status, Appointment.CANCELLED)
        self.assertEqual(len(sent_to("marta@example.com")), 3)
        self.assertEqual(self.owner_mail(), [])

    def test_unverified_owner_email_gets_nothing(self):
        get_user_model().objects.filter(pk=self.business.owner.pk).update(email_verified_at=None)
        self.book()
        self.assertEqual(self.owner_mail(), [])
        self.assertEqual(len(sent_to("laura@example.com")), 1)

    def test_email_failure_keeps_the_booking(self):
        with mock.patch("bookings.emails.send_mail", side_effect=OSError("smtp down")):
            response = self.book()
        self.assertEqual(Appointment.objects.count(), 1)
        self.assertEqual(response.status_code, 302)

    def test_another_business_owner_is_not_notified(self):
        other = create_business("b@example.com", "Otro")
        self.book()
        self.assertEqual(sent_to(other.owner.email), [])
