"""Public cancellation (baja) and withdrawal (arrepentimiento) buttons, end to end."""

import re
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from billing.models import Subscription
from bookings.tests.helpers import create_business
from legal.models import ServiceRequest

from .helpers import FakeProvider, renewing


def confirm_path(message):
    return re.search(r"https?://[^/\s]+(/solicitud/\S+/)", message.body).group(1)


@override_settings(BILLING_CONTACT_EMAIL="operador@turnofacil.example")
class ServiceRequestTests(TestCase):
    def setUp(self):
        self.business = create_business(email="luna@example.com")
        self.provider = FakeProvider()
        patcher = mock.patch("legal.services.get_provider", return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def ask(self, kind="cancel_request", email="luna@example.com"):
        return self.client.post(reverse(kind), {"email": email})

    def test_the_pages_need_no_login(self):
        for name in ("cancel_request", "withdrawal_request"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'name="email"')

    def test_the_code_is_sent_at_once_by_email_and_shown(self):
        response = self.ask()
        request = ServiceRequest.objects.get()
        self.assertTrue(request.code.startswith("TF-"))
        self.assertContains(response, request.code)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["luna@example.com"])
        self.assertIn(request.code, mail.outbox[0].subject)
        self.assertIn("/solicitud/", mail.outbox[0].body)
        self.assertIsNone(request.confirmed_at)

    def test_an_unknown_email_gets_the_same_screen_and_no_confirmation_link(self):
        known = self.ask().content.decode()
        unknown = self.ask(email="nadie@example.com")
        self.assertEqual(unknown.status_code, 200)
        request = ServiceRequest.objects.get(email="nadie@example.com")
        self.assertIsNone(request.business)
        self.assertNotIn("/solicitud/", mail.outbox[1].body)
        self.assertEqual(
            known.replace(ServiceRequest.objects.get(email="luna@example.com").code, "X").replace(
                "luna@example.com", "E"
            ),
            unknown.content.decode().replace(request.code, "X").replace("nadie@example.com", "E"),
        )

    def test_nothing_changes_until_the_mailbox_confirms(self):
        subscription = renewing(self.business)
        self.ask()
        subscription.refresh_from_db()
        self.assertTrue(subscription.renews_automatically)
        self.assertEqual(self.provider.cancelled, [])

    def test_confirming_a_cancellation_stops_the_renewal_and_sends_a_record(self):
        subscription = renewing(self.business)
        self.ask()
        path = confirm_path(mail.outbox[0])
        page = self.client.get(path)
        self.assertContains(page, "Confirmar")
        self.assertEqual(self.provider.cancelled, [])  # opening the link applies nothing

        done = self.client.post(path)
        self.assertContains(done, "Cortamos la renovación")
        subscription.refresh_from_db()
        self.assertFalse(subscription.renews_automatically)
        request = ServiceRequest.objects.get()
        self.assertEqual(request.outcome, ServiceRequest.RENEWAL_STOPPED)
        record = mail.outbox[-1]
        self.assertIn("Constancia", record.subject)
        self.assertEqual(record.to, ["luna@example.com"])

    def test_confirming_twice_changes_nothing_more(self):
        renewing(self.business)
        self.ask()
        path = confirm_path(mail.outbox[0])
        self.client.post(path)
        sent = len(mail.outbox)
        self.client.post(path)
        self.assertEqual(len(mail.outbox), sent)
        self.assertEqual(len(self.provider.cancelled), 1)

    def test_a_trial_has_nothing_to_charge(self):
        self.ask()
        self.client.post(confirm_path(mail.outbox[0]))
        self.assertEqual(ServiceRequest.objects.get().outcome, ServiceRequest.NOTHING_TO_CHARGE)
        self.assertEqual(Subscription.objects.get().status, Subscription.TRIALING)

    def test_withdrawal_within_ten_days_stops_the_renewal_and_flags_the_refund(self):
        subscription = renewing(self.business, contracted_days_ago=3)
        self.ask("withdrawal_request")
        self.client.post(confirm_path(mail.outbox[0]))
        request = ServiceRequest.objects.get()
        self.assertEqual(request.outcome, ServiceRequest.REFUND_DUE)
        self.assertTrue(request.needs_operator)
        subscription.refresh_from_db()
        self.assertFalse(subscription.renews_automatically)
        operator = [m for m in mail.outbox if m.to == ["operador@turnofacil.example"]]
        self.assertEqual(len(operator), 1)
        self.assertIn(request.code, operator[0].body)

    def test_withdrawal_after_ten_days_is_handled_as_a_cancellation(self):
        renewing(self.business, contracted_days_ago=15)
        self.ask("withdrawal_request")
        done = self.client.post(confirm_path(mail.outbox[0]))
        self.assertContains(done, "más de 10 días corridos")
        self.assertEqual(ServiceRequest.objects.get().outcome, ServiceRequest.OUT_OF_TERM)

    def test_a_provider_failure_goes_to_the_operator(self):
        self.provider.fail = True
        renewing(self.business)
        self.ask()
        self.client.post(confirm_path(mail.outbox[0]))
        self.assertEqual(ServiceRequest.objects.get().outcome, ServiceRequest.MANUAL_REVIEW)

    def test_a_forged_or_tampered_link_is_rejected(self):
        self.ask()
        path = confirm_path(mail.outbox[0])
        response = self.client.post(path[:-3] + "xx/")
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(ServiceRequest.objects.get().confirmed_at)

    def test_the_honeypot_and_the_rate_limit(self):
        self.client.post(reverse("cancel_request"), {"email": "luna@example.com", "website": "x"})
        self.assertFalse(ServiceRequest.objects.exists())
        for _ in range(5):
            self.ask()
        self.assertEqual(self.ask().status_code, 429)
        self.assertEqual(ServiceRequest.objects.count(), 5)
