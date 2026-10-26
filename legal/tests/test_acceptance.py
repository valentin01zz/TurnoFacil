"""Accepting the terms at signup and accepting new versions, with server-side evidence."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from bookings.tests.helpers import create_business
from legal.models import ImmutableError, LegalAcceptance, LegalDocument

from .helpers import publish

User = get_user_model()

SIGNUP = {
    "business_name": "Barbería Norte",
    "email": "norte@example.com",
    "password": "un-password-largo-123",
}


class SignupAcceptanceTests(TestCase):
    def signup(self, **extra):
        return self.client.post(reverse("signup"), {**SIGNUP, **extra})

    def test_without_published_terms_signup_works_as_before_and_records_nothing(self):
        response = self.signup()
        self.assertRedirects(response, reverse("verify_email_pending"))
        self.assertFalse(LegalAcceptance.objects.exists())
        self.client.logout()
        self.assertNotContains(self.client.get(reverse("signup")), "accept_terms")

    def test_the_box_is_shown_unticked(self):
        publish()
        page = self.client.get(reverse("signup"))
        self.assertContains(page, 'name="accept_terms"')
        self.assertNotContains(page, "checked")
        self.assertContains(page, reverse("terms"))

    def test_signup_without_the_box_is_rejected_on_the_server(self):
        publish()
        response = self.signup()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "tenés que aceptar los Términos y Condiciones")
        self.assertFalse(User.objects.exists())
        self.assertFalse(LegalAcceptance.objects.exists())

    def test_acceptance_records_the_exact_version_of_both_documents(self):
        terms = publish()
        privacy = publish(kind=LegalDocument.PRIVACY, body="Privacidad")
        self.signup(accept_terms="on", accept_privacy="on")
        user = User.objects.get()
        accepted = LegalAcceptance.objects.filter(user=user, action=LegalAcceptance.ACCEPTED)
        self.assertEqual({a.document for a in accepted}, {terms, privacy})
        self.assertEqual({a.context for a in accepted}, {LegalAcceptance.SIGNUP})

    def test_a_failed_signup_records_nothing(self):
        publish()
        self.signup(accept_terms="on", password="123")
        self.assertFalse(LegalAcceptance.objects.exists())

    def test_an_acceptance_cannot_be_edited(self):
        publish()
        self.signup(accept_terms="on")
        acceptance = LegalAcceptance.objects.get()
        acceptance.action = LegalAcceptance.INFORMED
        with self.assertRaises(ImmutableError):
            acceptance.save()


class ReacceptanceTests(TestCase):
    def setUp(self):
        self.business = create_business()
        self.client.force_login(self.business.owner)

    def test_existing_accounts_are_not_asked_while_there_are_no_terms(self):
        self.assertEqual(self.client.get(reverse("panel")).status_code, 200)

    def test_existing_accounts_accept_on_their_next_visit_and_nothing_is_backdated(self):
        terms = publish()
        self.assertFalse(LegalAcceptance.objects.exists())
        self.assertRedirects(self.client.get(reverse("panel")), reverse("accept_terms"))
        self.assertRedirects(self.client.get(reverse("service_list")), reverse("accept_terms"))

        refused = self.client.post(reverse("accept_terms"), {})
        self.assertContains(refused, "tenés que aceptar")
        self.assertFalse(LegalAcceptance.objects.exists())

        self.assertRedirects(
            self.client.post(reverse("accept_terms"), {"accept_terms": "on"}), reverse("panel")
        )
        acceptance = LegalAcceptance.objects.get()
        self.assertEqual(acceptance.document, terms)
        self.assertEqual(acceptance.context, LegalAcceptance.REACCEPTANCE)
        self.assertEqual(self.client.get(reverse("panel")).status_code, 200)

    def test_a_new_version_is_asked_again(self):
        first = publish(version="1.0")
        self.client.post(reverse("accept_terms"), {"accept_terms": "on"})
        self.assertEqual(self.client.get(reverse("panel")).status_code, 200)
        publish(version="2.0", body="Nuevos")
        self.assertRedirects(self.client.get(reverse("panel")), reverse("accept_terms"))
        self.client.post(reverse("accept_terms"), {"accept_terms": "on"})
        versions = LegalAcceptance.objects.values_list("document__version", flat=True)
        self.assertEqual(sorted(versions), ["1.0", "2.0"])
        self.assertTrue(LegalAcceptance.objects.filter(document=first).exists())

    def test_public_pages_are_never_blocked(self):
        publish()
        self.assertEqual(self.client.get(reverse("terms")).status_code, 200)
        self.assertEqual(self.client.get(reverse("cancel_request")).status_code, 200)
