import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class PasswordResetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("owner@example.com", "correct-horse-battery")

    def request_reset_link(self):
        self.client.post(reverse("password_reset"), {"email": "owner@example.com"})
        return re.search(r"https?://\S+", mail.outbox[0].body).group(0)

    def test_login_page_links_to_password_reset(self):
        response = self.client.get(reverse("login"))

        self.assertContains(response, reverse("password_reset"))

    def test_known_email_receives_a_reset_link(self):
        response = self.client.post(reverse("password_reset"), {"email": "owner@example.com"})

        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["owner@example.com"])
        self.assertIn("/password-reset/", mail.outbox[0].body)

    def test_unknown_email_gets_the_same_page_and_no_email(self):
        response = self.client.post(reverse("password_reset"), {"email": "nobody@example.com"})

        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_reset_link_sets_a_new_password(self):
        link = self.request_reset_link()

        form_page = self.client.get(link, follow=True)
        response = self.client.post(
            form_page.redirect_chain[-1][0],
            {"new_password1": "brand-new-secret-42", "new_password2": "brand-new-secret-42"},
        )

        self.assertRedirects(response, reverse("password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("brand-new-secret-42"))

    def test_invalid_link_shows_an_error(self):
        response = self.client.get(
            reverse("password_reset_confirm", args=["MQ", "invalid-token"]), follow=True
        )

        self.assertContains(response, "Link vencido o inválido")
