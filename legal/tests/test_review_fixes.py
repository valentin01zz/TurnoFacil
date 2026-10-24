"""Fixes from the review of PR #4: failed cancellations, failed emails, the 10-day term and
database-level protection of legal evidence."""

from datetime import datetime, time, timedelta
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.db import DatabaseError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from billing.models import SubscriptionEvent
from bookings.tests.helpers import create_business
from legal.models import LegalAcceptance, LegalDocument, ServiceRequest
from legal.services import within_withdrawal_term

from .helpers import FakeProvider, publish, renewing
from .test_service_requests import confirm_path

User = get_user_model()


def local(day, hour):
    return timezone.make_aware(datetime.combine(day, time(hour)))


def run(*args):
    out = StringIO()
    call_command(*args, stdout=out)
    return out.getvalue()


class BrokenProvider(FakeProvider):
    def cancel(self, subscription):
        raise RuntimeError("unexpected")


@override_settings(BILLING_CONTACT_EMAIL="operador@turnofacil.example")
class FailedCancellationTests(TestCase):
    def setUp(self):
        self.business = create_business(email="luna@example.com")
        self.provider = FakeProvider(fail=True)
        patcher = mock.patch("legal.services.get_provider", side_effect=lambda: self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def withdraw(self):
        self.client.post(reverse("withdrawal_request"), {"email": "luna@example.com"})
        return self.client.post(confirm_path(mail.outbox[0]))

    def test_a_withdrawal_in_term_whose_cancellation_fails_never_reads_as_stopped(self):
        subscription = renewing(self.business, contracted_days_ago=2)
        done = self.withdraw()
        request = ServiceRequest.objects.get()
        self.assertEqual(request.outcome, ServiceRequest.MANUAL_REVIEW)
        self.assertTrue(request.refund_due)
        self.assertTrue(request.needs_operator)
        self.assertContains(done, "Todavía no pudimos cortar la renovación")
        self.assertNotContains(done, "cortamos la renovación y te devolvemos")
        subscription.refresh_from_db()
        self.assertTrue(subscription.renews_automatically)
        operator = [m for m in mail.outbox if m.to == ["operador@turnofacil.example"]][0]
        self.assertIn("NO se cortó", operator.body)
        self.assertIn("Reembolso pendiente", operator.body)

    def test_an_unexpected_provider_error_goes_to_a_person_too(self):
        self.provider = BrokenProvider()
        renewing(self.business, contracted_days_ago=2)
        self.withdraw()
        request = ServiceRequest.objects.get()
        self.assertEqual(request.outcome, ServiceRequest.MANUAL_REVIEW)
        self.assertTrue(request.refund_due)


class WithdrawalTermTests(TestCase):
    def setUp(self):
        self.day = timezone.localdate() - timedelta(days=30)

    def test_counted_by_calendar_date_not_by_hours(self):
        contracted = local(self.day, 23)
        self.assertTrue(within_withdrawal_term(contracted, local(self.day + timedelta(10), 10)))
        self.assertTrue(within_withdrawal_term(contracted, local(self.day + timedelta(10), 23)))
        self.assertFalse(within_withdrawal_term(contracted, local(self.day + timedelta(11), 0)))

    @override_settings(BILLING_CONTACT_EMAIL="")
    def test_the_tenth_day_late_at_night_still_gets_the_refund(self):
        business = create_business(email="luna@example.com")
        provider = FakeProvider()
        with mock.patch("legal.services.get_provider", return_value=provider):
            subscription = renewing(business)
            # Contracted at 23:00 ten calendar days before the request (more than 240 hours).
            event = SubscriptionEvent.objects.filter(subscription=subscription).latest("pk")
            contracted = local(timezone.localdate() - timedelta(days=10), 23)
            SubscriptionEvent.objects.filter(pk=event.pk).update(created_at=contracted)
            self.client.post(reverse("withdrawal_request"), {"email": "luna@example.com"})
            ServiceRequest.objects.update(created_at=local(timezone.localdate(), 23))
            self.client.post(confirm_path(mail.outbox[0]))
        request = ServiceRequest.objects.get()
        self.assertEqual(request.outcome, ServiceRequest.REFUND_DUE)
        self.assertTrue(request.refund_due)


class FailedEmailTests(TestCase):
    def setUp(self):
        self.business = create_business(email="luna@example.com")
        self.provider = FakeProvider()
        patcher = mock.patch("legal.services.get_provider", return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_failed_code_email_is_told_on_screen_listed_and_can_be_resent(self):
        with mock.patch("legal.services.send_mail", side_effect=OSError("smtp down")):
            page = self.client.post(reverse("cancel_request"), {"email": "luna@example.com"})
        request = ServiceRequest.objects.get()
        self.assertContains(page, "No pudimos mandarte el email")
        self.assertContains(page, request.code)
        self.assertIsNone(request.received_email_sent_at)
        self.assertIn("EMAIL NO ENVIADO", run("service_requests"))

        run("service_requests", "--resend", request.code)
        request.refresh_from_db()
        self.assertIsNotNone(request.received_email_sent_at)
        self.assertIn("/solicitud/", mail.outbox[-1].body)
        self.assertEqual(run("service_requests").strip(), "Nothing pending.")

    def test_a_failed_record_is_resent_without_cancelling_twice(self):
        renewing(self.business)
        self.client.post(reverse("cancel_request"), {"email": "luna@example.com"})
        path = confirm_path(mail.outbox[0])
        with mock.patch("legal.services.send_mail", side_effect=OSError("smtp down")):
            self.client.post(path)
        request = ServiceRequest.objects.get()
        self.assertEqual(request.outcome, ServiceRequest.RENEWAL_STOPPED)
        self.assertIsNone(request.done_email_sent_at)
        self.assertIn("EMAIL NO ENVIADO", run("service_requests"))

        run("service_requests", "--resend", request.code)
        request.refresh_from_db()
        self.assertIsNotNone(request.done_email_sent_at)
        self.assertIn("Constancia", mail.outbox[-1].subject)
        self.assertEqual(len(self.provider.cancelled), 1)


class DatabaseProtectionTests(TestCase):
    def assertRefused(self, operation):
        with self.assertRaises(DatabaseError), transaction.atomic():
            operation()

    def test_published_documents_cannot_be_changed_even_in_bulk(self):
        publish()
        self.assertRefused(lambda: LegalDocument.objects.update(body="otro texto"))
        self.assertRefused(lambda: LegalDocument.objects.all().delete())
        self.assertTrue(LegalDocument.objects.get().body.startswith("# Términos"))

    def test_acceptances_cannot_be_changed_but_go_away_with_the_account(self):
        business = create_business()
        LegalAcceptance.objects.create(
            user=business.owner,
            document=publish(),
            action=LegalAcceptance.ACCEPTED,
            context=LegalAcceptance.SIGNUP,
        )
        self.assertRefused(lambda: LegalAcceptance.objects.update(action=LegalAcceptance.INFORMED))
        business.appointments.all().delete()
        owner = business.owner
        business.delete()
        owner.delete()
        self.assertFalse(LegalAcceptance.objects.exists())
        self.assertFalse(User.objects.filter(pk=owner.pk).exists())

    def test_service_requests_keep_working(self):
        request = ServiceRequest.objects.create(
            kind=ServiceRequest.CANCEL, code="TF-DDDD5555", email="a@example.com"
        )
        ServiceRequest.objects.filter(pk=request.pk).update(resolution_note="ok")
        request.refresh_from_db()
        self.assertEqual(request.resolution_note, "ok")
