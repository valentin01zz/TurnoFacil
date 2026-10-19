from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from businesses.models import Business

User = get_user_model()


def create_business(email, name):
    user = User.objects.create_user(email, "correct-horse-battery", verified=True)
    return Business.objects.create(owner=user, name=name)


class BusinessSlugTests(TestCase):
    def test_same_name_gets_a_different_slug(self):
        first = create_business("a@example.com", "Barbería Centro")
        second = create_business("b@example.com", "Barbería Centro")

        self.assertEqual(first.slug, "barberia-centro")
        self.assertEqual(second.slug, "barberia-centro-2")

    def test_name_without_letters_gets_a_fallback_slug(self):
        business = create_business("a@example.com", "!!!")

        self.assertEqual(business.slug, "negocio")


class PanelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business("a@example.com", "Estética Luna")
        cls.other = create_business("b@example.com", "Taller Sur")

    def test_panel_requires_login(self):
        response = self.client.get(reverse("panel"))

        self.assertRedirects(response, f"{reverse('login')}?next={reverse('panel')}")

    def test_panel_shows_the_public_booking_link(self):
        self.client.force_login(self.business.owner)

        response = self.client.get(reverse("panel"))

        self.assertContains(response, "http://testserver/b/estetica-luna/")

    def test_panel_shows_only_the_own_business(self):
        self.client.force_login(self.business.owner)

        response = self.client.get(reverse("panel"))

        self.assertContains(response, "Estética Luna")
        self.assertNotContains(response, "Taller Sur")
        self.assertNotContains(response, self.other.slug)


class BookingPageTests(TestCase):
    def test_existing_business_shows_its_page(self):
        create_business("a@example.com", "Estética Luna")

        response = self.client.get(reverse("booking_page", args=["estetica-luna"]))

        self.assertContains(response, "Estética Luna")
        self.assertContains(response, "todavía no está tomando reservas")

    def test_unknown_slug_returns_404(self):
        response = self.client.get(reverse("booking_page", args=["no-existe"]))

        self.assertEqual(response.status_code, 404)
