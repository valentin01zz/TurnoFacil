from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from businesses.models import Business

User = get_user_model()

VALID_DATA = {
    "business_name": "Estética Luna",
    "email": "owner@example.com",
    "password": "correct-horse-battery",
}


class SignupTests(TestCase):
    def test_valid_signup_creates_business_and_opens_panel(self):
        response = self.client.post(reverse("signup"), VALID_DATA, follow=True)

        self.assertRedirects(response, reverse("panel"))
        user = User.objects.get(email="owner@example.com")
        self.assertEqual(user.business.name, "Estética Luna")
        self.assertEqual(user.business.slug, "estetica-luna")
        self.assertEqual(response.context["user"], user)

    def test_password_is_stored_hashed(self):
        self.client.post(reverse("signup"), VALID_DATA)

        user = User.objects.get(email="owner@example.com")
        self.assertNotEqual(user.password, VALID_DATA["password"])
        self.assertTrue(user.check_password(VALID_DATA["password"]))

    def test_duplicate_email_is_rejected(self):
        self.client.post(reverse("signup"), VALID_DATA)
        self.client.post(reverse("logout"))

        data = {**VALID_DATA, "business_name": "Otro", "email": "OWNER@example.com"}
        response = self.client.post(reverse("signup"), data)

        self.assertContains(response, "Ya existe una cuenta con ese email.")
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Business.objects.count(), 1)

    def test_missing_business_name_is_rejected(self):
        response = self.client.post(reverse("signup"), {**VALID_DATA, "business_name": "  "})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors["business_name"])
        self.assertEqual(User.objects.count(), 0)

    def test_invalid_email_is_rejected(self):
        response = self.client.post(reverse("signup"), {**VALID_DATA, "email": "not-an-email"})

        self.assertTrue(response.context["form"].errors["email"])
        self.assertEqual(User.objects.count(), 0)

    def test_weak_password_is_rejected(self):
        response = self.client.post(reverse("signup"), {**VALID_DATA, "password": "12345"})

        self.assertTrue(response.context["form"].errors["password"])
        self.assertEqual(User.objects.count(), 0)

    def test_authenticated_user_is_sent_to_panel(self):
        self.client.post(reverse("signup"), VALID_DATA)

        response = self.client.get(reverse("signup"))

        self.assertRedirects(response, reverse("panel"))
