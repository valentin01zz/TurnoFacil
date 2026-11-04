"""Service prices (HU-33): optional, copied onto each appointment, shown to customers if chosen."""

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from bookings.models import Appointment
from bookings.tests.helpers import (
    create_appointment,
    create_business,
    create_professional,
    create_service,
    future_date,
    local_dt,
)
from businesses.models import Business, Service


class ServicePriceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business(name="Estética Luna")
        cls.ana = create_professional(cls.business, name="Ana")
        cls.date = future_date()

    def setUp(self):
        self.client.force_login(self.business.owner)

    def save_service(self, price, service=None):
        data = {"name": "Limpieza facial", "duration_minutes": "50", "is_active": "on"}
        data["price"] = price
        url = reverse("service_edit", args=[service.pk]) if service else reverse("service_create")
        return self.client.post(url, data)

    def test_price_is_optional(self):
        self.assertRedirects(self.save_service(""), reverse("service_list"))
        self.assertIsNone(Service.objects.get().price)

    def test_price_is_saved_and_listed(self):
        self.save_service("12500.50")
        self.assertEqual(Service.objects.get().price, Decimal("12500.50"))
        self.assertContains(self.client.get(reverse("service_list")), "12.500,50")

    def test_zero_negative_or_malformed_prices_are_rejected(self):
        for price in ["0", "-100", "abc", "1.234", "12345678901"]:
            with self.subTest(price=price):
                self.assertEqual(self.save_service(price).status_code, 200)
        self.assertFalse(Service.objects.exists())

    def test_database_rejects_a_non_positive_price(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Service.objects.create(
                business=self.business, name="X", duration_minutes=30, price=Decimal("0")
            )

    def test_online_booking_keeps_the_price_of_that_moment(self):
        service = create_service(self.business, duration=50)
        Service.objects.filter(pk=service.pk).update(price=Decimal("10000"))
        service.refresh_from_db()
        self.client.logout()
        self.client.post(
            reverse("book", args=[self.business.slug]),
            {
                "service": service.pk,
                "professional": self.ana.pk,
                "date": self.date.isoformat(),
                "start_at": local_dt(self.date, 10).isoformat(),
                "customer_name": "Laura Gómez",
                "customer_phone": "11 5555 1234",
                "customer_email": "laura@example.com",
            },
        )
        self.client.force_login(self.business.owner)
        self.save_service("15000", service=service)

        appointment = Appointment.objects.get()
        self.assertEqual(appointment.price, Decimal("10000"))
        self.client.post(
            reverse("appointment_reschedule", args=[appointment.pk]),
            {"professional": self.ana.pk, "date": self.date.isoformat(), "time": "15:00"},
        )
        appointment.refresh_from_db()
        self.assertEqual(appointment.start_at, local_dt(self.date, 15))
        self.assertEqual(appointment.price, Decimal("10000"))

    def test_manual_booking_copies_the_price_and_the_agenda_shows_it(self):
        service = create_service(self.business, duration=50)
        Service.objects.filter(pk=service.pk).update(price=Decimal("8000"))
        self.client.post(
            reverse("appointment_create"),
            {
                "customer_name": "Marta",
                "customer_phone": "11 4444 4444",
                "customer_email": "",
                "service": service.pk,
                "professional": self.ana.pk,
                "date": self.date.isoformat(),
                "time": "11:00",
            },
        )
        self.assertEqual(Appointment.objects.get().price, Decimal("8000"))
        response = self.client.get(reverse("panel"), {"date": self.date.isoformat()})
        self.assertContains(response, "$&nbsp;8.000")

    def test_service_without_price_books_without_price(self):
        service = create_service(self.business)
        appointment = create_appointment(self.ana, service, local_dt(self.date, 10))
        self.assertIsNone(appointment.price)
        response = self.client.get(reverse("panel"), {"date": self.date.isoformat()})
        self.assertNotContains(response, "$&nbsp;")


class PublicPriceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business(name="Estética Luna")
        create_professional(cls.business, name="Ana")
        cls.priced = create_service(cls.business, name="Limpieza facial")
        Service.objects.filter(pk=cls.priced.pk).update(price=Decimal("12500"))
        create_service(cls.business, name="Masaje")

    def booking_page(self):
        return self.client.get(reverse("booking_page", args=[self.business.slug]))

    def test_prices_are_hidden_by_default(self):
        self.assertFalse(self.business.show_prices)
        self.assertNotContains(self.booking_page(), "12.500")

    def test_owner_turns_prices_on_from_my_business(self):
        self.client.force_login(self.business.owner)
        self.client.post(
            reverse("business_edit"),
            {"name": "Estética Luna", "address": "", "show_prices": "on"},
        )
        self.business.refresh_from_db()
        self.assertTrue(self.business.show_prices)
        self.client.logout()
        response = self.booking_page()
        self.assertContains(response, "$&nbsp;12.500")
        self.assertContains(response, "Masaje")  # listed, just without a price

    def test_turning_it_off_hides_them_again(self):
        Business.objects.filter(pk=self.business.pk).update(show_prices=True)
        self.client.force_login(self.business.owner)
        self.client.post(reverse("business_edit"), {"name": "Estética Luna", "address": ""})
        self.client.logout()
        self.assertNotContains(self.booking_page(), "12.500")
