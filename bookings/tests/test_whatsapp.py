"""WhatsApp click-to-chat links (HU-32): ready-made messages the owner sends from their WhatsApp."""

from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from billing.tests.helpers import end_trial
from bookings.models import Appointment
from bookings.whatsapp import confirmation_url, reminder_url, whatsapp_number

from .helpers import (
    create_appointment,
    create_business,
    create_professional,
    create_service,
    future_date,
    local_dt,
    sent_to,
)


def message_of(url):
    return parse_qs(urlparse(url).query)["text"][0]


class WhatsappNumberTests(SimpleTestCase):
    def test_argentine_numbers_as_people_type_them(self):
        cases = {
            "11 5555-1234": "5491155551234",
            "011 15 5555 1234": "5491155551234",
            "(011) 15-5555-1234": "5491155551234",
            "+54 9 11 5555 1234": "5491155551234",
            "+54 11 5555 1234": "5491155551234",
            "5491155551234": "5491155551234",
            "0054 9 11 5555 1234": "5491155551234",
            "0351 15 512 3456": "5493515123456",
            "351 5123456": "5493515123456",
            "(0261) 15-412-3456": "5492614123456",
            "2944 15 123456": "5492944123456",
        }
        for phone, expected in cases.items():
            with self.subTest(phone=phone):
                self.assertEqual(whatsapp_number(phone), expected)

    def test_other_countries_are_used_as_typed(self):
        self.assertEqual(whatsapp_number("+1 415 555 0100"), "14155550100")
        self.assertEqual(whatsapp_number("+598 99 123 456"), "59899123456")

    def test_uncertain_numbers_get_no_link(self):
        for phone in ["5555 1234", "15 5555 1234", "123456", "11 5555 12345 6", "+1 23"]:
            with self.subTest(phone=phone):
                self.assertIsNone(whatsapp_number(phone))


class MessageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business(name="Estética Luna")
        cls.business.address = "Av. Siempre Viva 742"
        cls.business.save()
        cls.ana = create_professional(cls.business, name="Ana")
        cls.service = create_service(cls.business, name="Limpieza facial")
        cls.date = future_date()

    def appointment(self, phone="11 5555-1234"):
        appointment = create_appointment(self.ana, self.service, local_dt(self.date, 10))
        appointment.customer_name = "Laura Gómez"
        appointment.customer_phone = phone
        return appointment

    def test_confirmation_has_the_details_but_not_the_private_link(self):
        appointment = self.appointment()
        url = confirmation_url(appointment)
        self.assertTrue(url.startswith("https://wa.me/5491155551234?text="))
        text = message_of(url)
        for part in [
            "Hola Laura,",
            "Estética Luna",
            "confirmado",
            "Limpieza facial con Ana",
            "a las 10:00",
            f" {self.date.day} de ",
            "Av. Siempre Viva 742",
        ]:
            self.assertIn(part, text)
        self.assertNotIn(appointment.manage_token, url)
        self.assertNotIn("/t/", text)

    def test_reminder_text(self):
        text = message_of(reminder_url(self.appointment()))
        self.assertIn("recordarte", text)
        self.assertIn("a las 10:00", text)

    def test_unknown_number_gives_no_url(self):
        self.assertIsNone(confirmation_url(self.appointment(phone="5555 1234")))


class OwnerEmailLinkTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business("a@example.com", name="Estética Luna")
        cls.ana = create_professional(cls.business, name="Ana")
        cls.service = create_service(cls.business, name="Limpieza facial", duration=50)
        cls.date = future_date()

    def book(self, phone):
        return self.client.post(
            reverse("book", args=[self.business.slug]),
            {
                "service": self.service.pk,
                "professional": self.ana.pk,
                "date": self.date.isoformat(),
                "start_at": local_dt(self.date, 10).isoformat(),
                "customer_name": "Laura Gómez",
                "customer_phone": phone,
                "customer_email": "laura@example.com",
            },
        )

    def test_new_booking_email_has_the_whatsapp_link(self):
        self.book("011 15 5555 1234")
        [owner_mail] = sent_to("a@example.com")
        self.assertIn("confirmale por WhatsApp", owner_mail.body)
        self.assertIn("https://wa.me/5491155551234?text=", owner_mail.body)
        [customer_mail] = sent_to("laura@example.com")
        self.assertNotIn("wa.me", customer_mail.body)

    def test_unknown_number_leaves_the_link_out(self):
        self.book("5555 1234")
        [owner_mail] = sent_to("a@example.com")
        self.assertNotIn("wa.me", owner_mail.body)
        self.assertNotIn("WhatsApp", owner_mail.body)


class AgendaButtonTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business(name="Estética Luna")
        cls.ana = create_professional(cls.business, name="Ana")
        cls.service = create_service(cls.business, name="Limpieza facial", duration=50)

    def setUp(self):
        self.client.force_login(self.business.owner)

    def agenda(self, date):
        return self.client.get(reverse("panel"), {"date": date.isoformat()})

    def test_upcoming_appointment_has_the_button(self):
        date = future_date()
        create_appointment(self.ana, self.service, local_dt(date, 10))
        response = self.agenda(date)
        self.assertContains(response, 'href="https://wa.me/5491155555555?text=')
        self.assertContains(response, 'target="_blank"')

    def test_ended_or_cancelled_appointments_have_no_button(self):
        past = timezone.localdate() - timedelta(days=1)
        create_appointment(self.ana, self.service, local_dt(past, 10))
        create_appointment(
            self.ana, self.service, local_dt(future_date(), 11), status=Appointment.CANCELLED
        )
        self.assertNotContains(self.agenda(past), "wa.me")
        self.assertNotContains(self.agenda(future_date()), "wa.me")

    def test_read_only_account_keeps_the_button_without_edit_actions(self):
        date = future_date()
        create_appointment(self.ana, self.service, local_dt(date, 10))
        end_trial(self.business)
        response = self.agenda(date)
        self.assertContains(response, "wa.me")
        self.assertNotContains(response, "Reprogramar")
