import re
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail, signing
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.identity import canonical_email
from accounts.verification import make_token
from billing.models import Subscription

User = get_user_model()

SIGNUP = {
    "business_name": "Estética Luna",
    "email": "Ana.Perez@gmail.com",
    "password": "correct-horse-battery",
}


def link_from(message):
    return re.search(r"https?://\S+", message.body).group(0)


class CanonicalEmailTests(TestCase):
    def test_aliases_map_to_the_same_mailbox(self):
        self.assertEqual(canonical_email("Ana.Perez+prueba@Gmail.com"), "anaperez@gmail.com")
        self.assertEqual(canonical_email("anaperez@googlemail.com"), "anaperez@gmail.com")
        self.assertEqual(canonical_email("ana+x@empresa.com.ar"), "ana@empresa.com.ar")
        self.assertEqual(canonical_email("ana.perez@empresa.com.ar"), "ana.perez@empresa.com.ar")


class SignupVerificationTests(TestCase):
    def signup(self, **overrides):
        return self.client.post(reverse("signup"), {**SIGNUP, **overrides})

    def test_signup_sends_a_verification_link_and_does_not_start_the_trial(self):
        response = self.signup()

        self.assertRedirects(response, reverse("verify_email_pending"))
        user = User.objects.get(email="ana.perez@gmail.com")
        self.assertFalse(user.is_email_verified)
        self.assertFalse(Subscription.objects.filter(business__owner=user).exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ana.perez@gmail.com"])
        self.assertIn("/verificar-email/", mail.outbox[0].body)

    def test_unverified_owner_cannot_use_the_panel_and_takes_no_bookings(self):
        self.signup()
        user = User.objects.get(email="ana.perez@gmail.com")

        for name in ("panel", "service_list", "service_create", "plans"):
            response = self.client.get(reverse(name))
            self.assertRedirects(response, reverse("verify_email_pending"), msg_prefix=name)
        page = self.client.get(reverse("booking_page", args=[user.business.slug]))
        self.assertContains(page, "todavía no está tomando reservas")

    def test_confirming_starts_the_trial_and_opens_the_panel(self):
        self.signup()

        response = self.client.get(link_from(mail.outbox[0]), follow=True)

        self.assertRedirects(response, reverse("panel"))
        self.assertContains(response, "empezó tu prueba gratis")
        user = User.objects.get(email="ana.perez@gmail.com")
        self.assertTrue(user.is_email_verified)
        subscription = Subscription.objects.get(business__owner=user)
        self.assertEqual(
            subscription.trial_ends_at - subscription.trial_started_at, timedelta(days=14)
        )

    def test_confirming_twice_does_not_restart_the_trial(self):
        self.signup()
        link = link_from(mail.outbox[0])
        self.client.get(link)
        first = Subscription.objects.get(business__owner__email="ana.perez@gmail.com")

        self.client.get(link)

        again = Subscription.objects.get(pk=first.pk)
        self.assertEqual(again.trial_ends_at, first.trial_ends_at)
        self.assertEqual(Subscription.objects.count(), 1)

    def test_confirming_while_logged_out_sends_to_login(self):
        self.signup()
        link = link_from(mail.outbox[0])
        self.client.logout()

        response = self.client.get(link)

        self.assertRedirects(response, reverse("login"))
        self.assertTrue(User.objects.get(email="ana.perez@gmail.com").is_email_verified)

    def test_altered_or_expired_links_are_rejected(self):
        self.signup()
        user = User.objects.get(email="ana.perez@gmail.com")
        token = make_token(user)

        altered = self.client.get(reverse("verify_email", args=[token[:-2] + "xx"]))
        forged = self.client.get(
            reverse("verify_email", args=[signing.dumps({"u": user.pk, "e": user.email_canonical})])
        )
        with mock.patch(
            "django.core.signing.time.time", return_value=timezone.now().timestamp() + 4 * 86400
        ):
            expired = self.client.get(reverse("verify_email", args=[token]))

        for response in (altered, forged, expired):
            self.assertContains(response, "Link vencido o inválido", status_code=400)
        user.refresh_from_db()
        self.assertFalse(user.is_email_verified)

    def test_aliases_of_an_existing_mailbox_cannot_sign_up_again(self):
        self.signup()
        self.client.logout()

        for alias in (
            "anaperez@gmail.com",
            "ana.perez+trial2@gmail.com",
            "ANA.PEREZ@googlemail.com",
        ):
            response = self.signup(email=alias, business_name="Otro negocio")
            self.assertContains(response, "Ya existe una cuenta con ese email.", msg_prefix=alias)
        self.assertEqual(User.objects.count(), 1)

    def test_login_of_an_unverified_owner_lands_on_the_confirmation_page(self):
        self.signup()
        self.client.logout()

        response = self.client.post(
            reverse("login"),
            {"username": "ana.perez@gmail.com", "password": "correct-horse-battery"},
            follow=True,
        )

        self.assertRedirects(response, reverse("verify_email_pending"))
        self.assertContains(response, "Confirmá tu email")


class ResendTests(TestCase):
    def setUp(self):
        self.client.post(reverse("signup"), SIGNUP)
        mail.outbox.clear()

    def test_resend_is_throttled(self):
        response = self.client.post(reverse("resend_verification"), follow=True)

        self.assertContains(response, "Esperá un minuto")
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_VERIFICATION_RESEND_SECONDS=0)
    def test_resend_sends_a_new_link(self):
        response = self.client.post(reverse("resend_verification"), follow=True)

        self.assertContains(response, "Te mandamos un link nuevo")
        self.assertEqual(len(mail.outbox), 1)
        self.client.get(link_from(mail.outbox[0]))
        self.assertTrue(User.objects.get(email="ana.perez@gmail.com").is_email_verified)

    def test_resend_requires_post(self):
        self.assertEqual(self.client.get(reverse("resend_verification")).status_code, 405)


class ExistingAccountsMigrationTests(TestCase):
    def test_existing_accounts_are_marked_verified(self):
        from django.apps import apps as django_apps

        fill = __import__("accounts.migrations.0002_email_verification", fromlist=["fill"]).fill
        user = User.objects.create_user("Vieja.Cuenta@gmail.com", "correct-horse-battery")
        User.objects.filter(pk=user.pk).update(email_verified_at=None, email_canonical="x")

        fill(django_apps, None)

        user.refresh_from_db()
        self.assertEqual(user.email_verified_at, user.date_joined)
        self.assertEqual(user.email_canonical, "viejacuenta@gmail.com")
