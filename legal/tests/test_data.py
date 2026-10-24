"""Operator commands to answer data requests: export, erase, delete and purge."""

import json
from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from bookings.models import Appointment
from bookings.tests.helpers import (
    create_appointment,
    create_business,
    create_professional,
    create_service,
)
from businesses.models import Business
from legal.models import LegalAcceptance, ServiceRequest

from .helpers import publish, renewing

User = get_user_model()


def run(*args):
    out = StringIO()
    call_command(*args, stdout=out)
    return out.getvalue()


class DataCommandTests(TestCase):
    def setUp(self):
        self.business = create_business(email="luna@example.com")
        self.ana = create_professional(self.business)
        self.service = create_service(self.business)
        self.other = create_business(email="sol@example.com", name="Sol")
        other_pro = create_professional(self.other)
        self.other_appointment = create_appointment(
            other_pro, create_service(self.other), timezone.now() + timedelta(days=3)
        )

    def past(self, days=30):
        start = timezone.now() - timedelta(days=days)
        return create_appointment(self.ana, self.service, start)

    def test_export_has_the_business_data_and_never_another_business(self):
        self.past()
        LegalAcceptance.objects.create(
            user=self.business.owner,
            document=publish(),
            action=LegalAcceptance.ACCEPTED,
            context=LegalAcceptance.SIGNUP,
        )
        data = json.loads(run("export_business_data", self.business.slug))
        self.assertEqual(data["cuenta"]["email"], "luna@example.com")
        self.assertEqual(len(data["turnos"]), 1)
        self.assertEqual(data["aceptaciones"][0]["documento"], "Términos y Condiciones v1.0")
        self.assertNotIn("Sol", json.dumps(data))
        self.assertNotIn("password", json.dumps(data))

    def test_customer_data_shows_only_that_customer(self):
        self.past()
        mine = Appointment.objects.filter(business=self.business).first()
        Appointment.objects.filter(pk=mine.pk).update(customer_email="otra@example.com")
        data = json.loads(run("customer_data", "otra@example.com"))
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["negocio"], self.business.name)

    def test_erasing_a_customer_keeps_future_appointments(self):
        old = self.past()
        output = run("customer_data", "cliente@example.com", "--erase")
        old.refresh_from_db()
        self.assertEqual(old.customer_email, "")
        self.assertEqual(old.customer_phone, "")
        self.assertIn("1 future appointment", output)
        self.other_appointment.refresh_from_db()
        self.assertEqual(self.other_appointment.customer_email, "cliente@example.com")

    def test_delete_business_needs_yes_and_a_stopped_renewal(self):
        self.past()
        with self.assertRaises(CommandError):
            run("delete_business", self.business.slug)
        renewing(self.business)
        with self.assertRaises(CommandError):
            run("delete_business", self.business.slug, "--yes")
        self.assertTrue(Business.objects.filter(pk=self.business.pk).exists())

    def test_delete_business_removes_it_its_owner_and_its_appointments_only(self):
        self.past()
        ServiceRequest.objects.create(
            kind=ServiceRequest.CANCEL,
            code="TF-AAAA2222",
            email="luna@example.com",
            business=self.business,
        )
        run("delete_business", self.business.slug, "--yes")
        self.assertFalse(Business.objects.filter(slug=self.business.slug).exists())
        self.assertFalse(User.objects.filter(email="luna@example.com").exists())
        self.assertFalse(Appointment.objects.filter(business_id=self.business.pk).exists())
        self.assertTrue(Appointment.objects.filter(pk=self.other_appointment.pk).exists())
        self.assertIsNone(ServiceRequest.objects.get().business)

    def test_purge_does_nothing_until_the_period_is_decided(self):
        self.past(days=400)
        self.assertIn("nothing deleted", run("purge_old_data"))
        self.assertEqual(Appointment.objects.filter(business=self.business).count(), 1)

    @override_settings(APPOINTMENT_RETENTION_DAYS=365)
    def test_purge_deletes_only_what_is_older_than_the_period(self):
        self.past(days=400)
        recent = self.past(days=10)
        run("purge_old_data")
        self.assertEqual(list(Appointment.objects.filter(business=self.business)), [recent])
        self.assertTrue(Appointment.objects.filter(pk=self.other_appointment.pk).exists())


class ServiceRequestsCommandTests(TestCase):
    def test_lists_what_needs_the_operator_and_resolves_it(self):
        request = ServiceRequest.objects.create(
            kind=ServiceRequest.WITHDRAWAL,
            code="TF-BBBB3333",
            email="a@example.com",
            confirmed_at=timezone.now(),
            outcome=ServiceRequest.REFUND_DUE,
        )
        self.assertIn("TF-BBBB3333", run("service_requests"))
        with self.assertRaises(CommandError):
            run("service_requests", "--resolve", "TF-BBBB3333")
        run("service_requests", "--resolve", "TF-BBBB3333", "--note", "Reembolso hecho en MP")
        request.refresh_from_db()
        self.assertIsNotNone(request.resolved_at)
        self.assertEqual(run("service_requests").strip(), "Nothing pending.")

    def test_unconfirmed_requests_older_than_a_day_are_listed(self):
        ServiceRequest.objects.create(
            kind=ServiceRequest.CANCEL,
            code="TF-CCCC4444",
            email="a@example.com",
            created_at=timezone.now() - timedelta(days=2),
        )
        self.assertIn("Sin confirmar", run("service_requests"))
