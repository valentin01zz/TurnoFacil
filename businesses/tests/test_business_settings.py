from django.core import mail
from django.test import TestCase
from django.urls import reverse

from bookings.emails import send_confirmation
from bookings.tests.helpers import (
    create_appointment,
    create_business,
    create_professional,
    create_service,
    future_date,
    local_dt,
)


class BusinessSettingsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business(name="Estética Luna")
        cls.other = create_business("b@example.com", "Taller Sur")

    def setUp(self):
        self.client.force_login(self.business.owner)

    def test_page_requires_login(self):
        self.client.logout()
        url = reverse("business_edit")

        self.assertRedirects(self.client.get(url), f"{reverse('login')}?next={url}")

    def test_owner_saves_name_and_address(self):
        response = self.client.post(
            reverse("business_edit"),
            {"name": "Estética  Luna\nCentro", "address": "Av. Corrientes 1234,\r\nPalermo"},
        )

        self.assertContains(response, "Listo, guardamos los cambios.")
        self.business.refresh_from_db()
        self.assertEqual(self.business.name, "Estética Luna Centro")
        self.assertEqual(self.business.address, "Av. Corrientes 1234, Palermo")
        self.assertEqual(self.business.slug, "estetica-luna")

    def test_page_shows_the_current_values(self):
        self.business.address = "Av. Corrientes 1234"
        self.business.save()

        response = self.client.get(reverse("business_edit"))

        self.assertContains(response, 'value="Av. Corrientes 1234"')

    def test_name_is_required(self):
        response = self.client.post(reverse("business_edit"), {"name": "  ", "address": ""})

        self.assertTrue(response.context["form"].errors["name"])
        self.business.refresh_from_db()
        self.assertEqual(self.business.name, "Estética Luna")

    def test_only_the_own_business_changes(self):
        self.client.post(reverse("business_edit"), {"name": "Nuevo", "address": "Calle 1"})

        self.other.refresh_from_db()
        self.assertEqual(self.other.name, "Taller Sur")
        self.assertEqual(self.other.address, "")


class AddressVisibilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business(name="Estética Luna")
        cls.ana = create_professional(cls.business, name="Ana")
        cls.service = create_service(cls.business)

    def booking_page(self):
        return self.client.get(reverse("booking_page", args=[self.business.slug]))

    def test_booking_page_shows_the_address(self):
        self.business.address = "Av. Corrientes 1234"
        self.business.save()

        self.assertContains(self.booking_page(), "Av. Corrientes 1234")

    def test_booking_page_without_address_shows_no_empty_chip(self):
        self.assertNotContains(self.booking_page(), 'class="chip"')

    def test_emails_include_the_address_only_when_set(self):
        appointment = create_appointment(self.ana, self.service, local_dt(future_date(), 9, 0))

        send_confirmation(appointment, "http://testserver/t/x/")
        self.business.address = "Av. Corrientes 1234"
        self.business.save()
        appointment.refresh_from_db()
        send_confirmation(appointment, "http://testserver/t/x/")

        self.assertNotIn("Dirección", mail.outbox[0].body)
        self.assertIn("Dirección: Av. Corrientes 1234", mail.outbox[1].body)
