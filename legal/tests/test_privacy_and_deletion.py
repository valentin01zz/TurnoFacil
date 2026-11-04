"""The privacy box in signup and booking, and the public data deletion request.

Added in the Founder's audit of 2026-10-26 (LEGAL_REVIEW.md, section 7.5).
"""

import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from bookings.models import Appointment
from bookings.tests.helpers import (
    create_business,
    create_professional,
    create_service,
    future_date,
    local_dt,
)
from legal.models import LegalAcceptance, LegalDocument, ServiceRequest

from .helpers import publish

User = get_user_model()

SIGNUP = {
    "business_name": "Barbería Norte",
    "email": "norte@example.com",
    "password": "un-password-largo-123",
}


def confirm_path(message):
    return re.search(r"https?://[^/\s]+(/solicitud/\S+/)", message.body).group(1)


class SignupPrivacyBoxTests(TestCase):
    def signup(self, **extra):
        return self.client.post(reverse("signup"), {**SIGNUP, **extra})

    def test_no_box_until_the_policy_is_published(self):
        self.assertNotContains(self.client.get(reverse("signup")), "accept_privacy")

    def test_the_box_is_shown_unticked_and_links_the_policy(self):
        publish(kind=LegalDocument.PRIVACY, body="Privacidad")
        page = self.client.get(reverse("signup"))
        self.assertContains(page, 'name="accept_privacy"')
        self.assertNotContains(page, "checked")
        self.assertContains(page, reverse("privacy"))

    def test_signup_without_the_box_is_rejected_on_the_server(self):
        publish(kind=LegalDocument.PRIVACY, body="Privacidad")
        response = self.signup()
        self.assertContains(response, "tenés que aceptar la Política de Privacidad")
        self.assertFalse(User.objects.exists())

    def test_ticking_it_records_the_exact_version_as_accepted(self):
        privacy = publish(kind=LegalDocument.PRIVACY, body="Privacidad")
        self.signup(accept_privacy="on")
        accepted = LegalAcceptance.objects.get(user=User.objects.get())
        self.assertEqual(accepted.document, privacy)
        self.assertEqual(accepted.action, LegalAcceptance.ACCEPTED)


class BookingPrivacyBoxTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.business = create_business()
        cls.ana = create_professional(cls.business, name="Ana")
        cls.service = create_service(cls.business)
        cls.date = future_date()

    def booking_data(self, **overrides):
        data = {
            "service": self.service.pk,
            "professional": self.ana.pk,
            "date": self.date.isoformat(),
            "start_at": local_dt(self.date, 9).isoformat(),
            "customer_name": "Laura Gómez",
            "customer_phone": "+54 11 5555-1234",
            "customer_email": "laura@example.com",
            "website": "",
        }
        data.update(overrides)
        return data

    def book(self, **overrides):
        return self.client.post(
            reverse("book", args=[self.business.slug]), self.booking_data(**overrides)
        )

    def page_with_slots(self):
        query = f"?service={self.service.pk}&professional={self.ana.pk}&date={self.date}"
        return self.client.get(reverse("booking_page", args=[self.business.slug]) + query)

    def test_without_a_published_policy_booking_works_as_before(self):
        self.assertNotContains(self.page_with_slots(), "accept_privacy")
        self.book()
        self.assertEqual(Appointment.objects.count(), 1)

    def test_the_box_is_shown_unticked(self):
        publish(kind=LegalDocument.PRIVACY, body="Privacidad")
        page = self.page_with_slots()
        self.assertContains(page, 'name="accept_privacy"')
        self.assertNotRegex(page.content.decode(), r'name="accept_privacy"[^>]*checked')

    def test_booking_without_the_box_is_rejected_on_the_server(self):
        publish(kind=LegalDocument.PRIVACY, body="Privacidad")
        response = self.book()
        self.assertContains(response, "tenés que aceptar la Política de Privacidad")
        self.assertFalse(Appointment.objects.exists())

    def test_booking_with_the_box_ticked_works(self):
        publish(kind=LegalDocument.PRIVACY, body="Privacidad")
        self.book(accept_privacy="on")
        self.assertEqual(Appointment.objects.count(), 1)


@override_settings(BILLING_CONTACT_EMAIL="operador@turnofacil.example")
class DeletionRequestTests(TestCase):
    def ask(self, email):
        return self.client.post(reverse("deletion_request"), {"email": email})

    def test_the_page_needs_no_login_and_is_in_every_footer(self):
        page = self.client.get(reverse("deletion_request"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'name="email"')
        self.assertContains(self.client.get(reverse("home")), reverse("deletion_request"))
        business = create_business()
        booking_page = self.client.get(reverse("booking_page", args=[business.slug]))
        self.assertContains(booking_page, reverse("deletion_request"))

    def test_a_customer_without_an_account_gets_a_confirmation_link(self):
        self.ask("laura@example.com")
        request = ServiceRequest.objects.get()
        self.assertEqual(request.kind, ServiceRequest.DELETION)
        self.assertIsNone(request.business)
        self.assertIn("/solicitud/", mail.outbox[0].body)
        self.assertIn(request.code, mail.outbox[0].subject)

    def test_nothing_happens_until_the_mailbox_confirms(self):
        self.ask("laura@example.com")
        request = ServiceRequest.objects.get()
        self.assertIsNone(request.confirmed_at)
        self.assertFalse(request.needs_operator)
        self.assertEqual(len(mail.outbox), 1)

    def test_confirming_hands_it_to_the_operator_and_sends_the_record(self):
        business = create_business(email="luna@example.com")
        self.ask("luna@example.com")
        path = confirm_path(mail.outbox[0])
        page = self.client.post(path)
        self.assertContains(page, "dentro de los 5 días hábiles")
        request = ServiceRequest.objects.get()
        self.assertEqual(request.outcome, ServiceRequest.DELETION_PENDING)
        self.assertTrue(request.needs_operator)
        record, notice = mail.outbox[1], mail.outbox[2]
        self.assertEqual(record.to, ["luna@example.com"])
        self.assertIn("5 días hábiles", record.body)
        self.assertEqual(notice.to, ["operador@turnofacil.example"])
        self.assertIn(f"delete_business {business.slug} --yes", notice.body)
        self.assertIn("customer_data luna@example.com --erase", notice.body)
        # Nothing is deleted by itself: the operator does it.
        self.assertTrue(User.objects.filter(pk=business.owner.pk).exists())

    def test_it_is_listed_for_the_operator_until_resolved(self):
        from io import StringIO

        from django.core.management import call_command

        self.ask("laura@example.com")
        self.client.post(confirm_path(mail.outbox[0]))
        code = ServiceRequest.objects.get().code
        out = StringIO()
        call_command("service_requests", stdout=out)
        self.assertIn(code, out.getvalue())
        self.assertIn("Borrado pendiente", out.getvalue())
        call_command("service_requests", resolve=code, note="Datos borrados", stdout=StringIO())
        out = StringIO()
        call_command("service_requests", stdout=out)
        self.assertNotIn(code, out.getvalue())
