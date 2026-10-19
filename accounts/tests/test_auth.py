from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from businesses.models import Business

User = get_user_model()

PASSWORD = "correct-horse-battery"


class AuthTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("owner@example.com", PASSWORD, verified=True)
        Business.objects.create(owner=cls.user, name="Estética Luna")

    def test_login_with_valid_credentials_opens_panel(self):
        response = self.client.post(
            reverse("login"), {"username": "owner@example.com", "password": PASSWORD}
        )

        self.assertRedirects(response, reverse("panel"))

    def test_login_ignores_email_case(self):
        response = self.client.post(
            reverse("login"), {"username": "Owner@Example.com", "password": PASSWORD}
        )

        self.assertRedirects(response, reverse("panel"))

    def test_login_with_wrong_password_fails(self):
        response = self.client.post(
            reverse("login"), {"username": "owner@example.com", "password": "wrong-password"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(response.context["user"].is_authenticated)

    def test_logout_ends_the_session(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("home"))
        panel = self.client.get(reverse("panel"))
        self.assertRedirects(panel, f"{reverse('login')}?next={reverse('panel')}")

    def test_logout_rejects_get(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("logout"))

        self.assertEqual(response.status_code, 405)

    def test_home_shows_signup_and_login_links(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, reverse("signup"))
        self.assertContains(response, reverse("login"))
