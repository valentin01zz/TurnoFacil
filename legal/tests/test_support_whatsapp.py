"""TurnoFacil's own support WhatsApp: contact page button and account menu item."""

from urllib.parse import parse_qs, urlparse

from django.test import TestCase, override_settings
from django.urls import reverse

from bookings.tests.helpers import create_business

SUPPORT = "264 674-4363"
CHAT = "https://wa.me/5492646744363?text="


def message_of(url):
    return parse_qs(urlparse(url).query)["text"][0]


def chat_links(response):
    html = response.content.decode()
    return [part.split('"', 1)[0] for part in html.split('href="')[1:] if part.startswith(CHAT)]


@override_settings(LEGAL_CONTACT_EMAIL="hola@turnofacil.example")
class ContactPageButtonTests(TestCase):
    def test_no_button_without_the_setting(self):
        with self.settings(SUPPORT_WHATSAPP=""):
            response = self.client.get(reverse("contact"))
        self.assertNotContains(response, "wa.me")
        self.assertNotContains(response, "Escribinos por WhatsApp")

    def test_button_opens_the_support_chat_with_a_message(self):
        with self.settings(SUPPORT_WHATSAPP=SUPPORT):
            response = self.client.get(reverse("contact"))
        self.assertContains(response, "Escribinos por WhatsApp")
        [link] = chat_links(response)
        self.assertEqual(message_of(link), "Hola, tengo una consulta sobre TurnoFacil.")
        self.assertContains(response, 'target="_blank" rel="noopener noreferrer"')

    def test_a_number_that_is_not_certain_shows_no_button(self):
        with self.settings(SUPPORT_WHATSAPP="15 5555 1234"):
            response = self.client.get(reverse("contact"))
        self.assertNotContains(response, "wa.me")


class AccountMenuTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business(name="Peluquería Sol & Luna")

    def setUp(self):
        self.client.force_login(self.business.owner)

    def test_owner_gets_help_with_the_business_name_in_the_message(self):
        with self.settings(SUPPORT_WHATSAPP=SUPPORT):
            response = self.client.get(reverse("panel"))
        self.assertContains(response, "Ayuda por WhatsApp")
        [link] = chat_links(response)
        self.assertEqual(
            message_of(link),
            "Hola, soy de Peluquería Sol & Luna y necesito ayuda con TurnoFacil.",
        )
        # The name is URL-encoded, so it cannot break out of the link or add parameters.
        self.assertIn("Sol%20%26%20Luna", link)

    def test_no_menu_item_without_the_setting(self):
        with self.settings(SUPPORT_WHATSAPP=""):
            response = self.client.get(reverse("panel"))
        self.assertNotContains(response, "Ayuda por WhatsApp")
        self.assertEqual(chat_links(response), [])


class CustomerPagesTests(TestCase):
    """Customers book with the business: TurnoFacil's support number is never offered to them."""

    @classmethod
    def setUpTestData(cls):
        cls.business = create_business()

    def test_booking_page_has_no_support_link(self):
        with self.settings(SUPPORT_WHATSAPP=SUPPORT):
            response = self.client.get(reverse("booking_page", args=[self.business.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(chat_links(response), [])
