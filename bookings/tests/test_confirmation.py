import re
from unittest import mock

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from bookings.emails import send_confirmation
from bookings.models import Appointment
from businesses.models import Business

from .helpers import (
    create_appointment,
    create_business,
    create_professional,
    create_service,
    future_date,
    local_dt,
    sent_to,
)


class ConfirmationEmailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business(name="Estética Luna")
        cls.ana = create_professional(cls.business, name="Ana")
        cls.service = create_service(cls.business, name="Limpieza facial", duration=50)
        cls.date = future_date()

    def book(self, hour=10, email="laura@example.com"):
        start_at = local_dt(self.date, hour, 0)
        return self.client.post(
            reverse("book", args=[self.business.slug]),
            {
                "service": self.service.pk,
                "date": self.date.isoformat(),
                "start_at": start_at.isoformat(),
                "customer_name": "Laura Gómez",
                "customer_phone": "11 5555 1234",
                "customer_email": email,
            },
        )

    def test_booking_sends_the_details_and_management_link(self):
        response = self.book()

        appointment = Appointment.objects.get()
        customer_mail = sent_to("laura@example.com")
        self.assertEqual(len(customer_mail), 1)
        message = customer_mail[0]
        self.assertEqual(message.to, ["laura@example.com"])
        self.assertEqual(message.subject, "Turno confirmado en Estética Luna")
        for text in ["Laura Gómez", "Estética Luna", "Limpieza facial", "Ana", "10:00"]:
            self.assertIn(text, message.body)
        weekday_and_day = f"{self.date.day} de"
        self.assertIn(weekday_and_day, message.body)
        path = f"/t/{appointment.manage_token}/"
        self.assertIn(f"http://testserver{path}", message.body)
        self.assertRedirects(response, f"{path}?nuevo=1")

    def test_management_link_opens_only_that_appointment(self):
        self.book(hour=10, email="laura@example.com")
        self.book(hour=11, email="marta@example.com")

        customer_mail = sent_to("laura@example.com") + sent_to("marta@example.com")
        links = [re.search(r"http://testserver(/t/\S+/)", m.body).group(1) for m in customer_mail]
        first, second = (self.client.get(link) for link in links)

        self.assertNotEqual(links[0], links[1])
        self.assertContains(first, "10:00")
        self.assertNotContains(first, "11:00")
        self.assertContains(second, "11:00")

    def test_email_failure_does_not_lose_the_booking(self):
        with (
            mock.patch("bookings.emails.send_mail", side_effect=OSError("smtp down")),
            self.assertLogs("bookings.emails", level="ERROR"),
        ):
            response = self.book()

        self.assertEqual(Appointment.objects.count(), 1)
        self.assertEqual(response.status_code, 302)

    def test_appointment_without_email_sends_nothing(self):
        appointment = create_appointment(self.ana, self.service, local_dt(self.date, 9, 0))
        appointment.customer_email = ""

        send_confirmation(appointment, "http://testserver/t/x/")

        self.assertEqual(len(mail.outbox), 0)

    def test_unknown_or_altered_link_shows_not_found_without_data(self):
        self.book()
        token = Appointment.objects.get().manage_token

        for bad in ["no-existe", token[:-1], token + "x"]:
            response = self.client.get(reverse("appointment_detail", args=[bad]))
            self.assertEqual(response.status_code, 404, bad)
            self.assertContains(response, "Turno no encontrado", status_code=404)
            self.assertNotContains(response, "Laura", status_code=404)
            self.assertNotContains(response, "Limpieza facial", status_code=404)


class EmailSubjectTests(TestCase):
    def test_subject_with_a_line_break_is_still_sent_on_one_line(self):
        business = create_business(name="Estética Luna")
        Business.objects.filter(pk=business.pk).update(name="Estética\nLuna")
        business.refresh_from_db()
        ana = create_professional(business, name="Ana")
        service = create_service(business)
        appointment = create_appointment(ana, service, local_dt(future_date(), 9, 0))

        send_confirmation(appointment, "http://testserver/t/x/")

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Turno confirmado en Estética Luna")
