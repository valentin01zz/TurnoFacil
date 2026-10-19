"""Phase 9: existing businesses and the safety of the billing migrations."""

from django.apps import apps as django_apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from billing.access import get_access
from billing.models import Subscription
from bookings.models import Appointment
from bookings.tests.helpers import (
    create_appointment,
    create_business,
    create_professional,
    create_service,
    future_date,
    local_dt,
)
from businesses.models import Professional, Service

SEED = __import__("billing.migrations.0002_seed_plans_and_trials", fromlist=["seed"]).seed


class ExistingBusinessTests(TestCase):
    """A business that existed before plans keeps all its data and keeps working afterwards."""

    def setUp(self):
        self.business = create_business(name="Barbería Existente")
        self.ana = create_professional(self.business, name="Ana")
        self.service = create_service(self.business, name="Corte")
        self.appointment = create_appointment(self.ana, self.service, local_dt(future_date(), 10))
        # Simulate the state before the billing app existed: no subscription at all.
        Subscription.objects.filter(business=self.business).delete()

    def test_migration_adds_a_trial_without_touching_operational_data(self):
        SEED(django_apps, None)

        self.assertEqual(Subscription.objects.get(business=self.business).status, "trialing")
        self.assertTrue(Professional.objects.filter(pk=self.ana.pk, is_active=True).exists())
        self.assertTrue(Service.objects.filter(pk=self.service.pk, is_active=True).exists())
        self.appointment.refresh_from_db()
        self.assertTrue(self.appointment.is_confirmed)

    def test_running_the_migration_twice_changes_nothing(self):
        SEED(django_apps, None)
        first = Subscription.objects.get(business=self.business)

        SEED(django_apps, None)

        again = Subscription.objects.get(business=self.business)
        self.assertEqual(again.pk, first.pk)
        self.assertEqual(again.trial_ends_at, first.trial_ends_at)

    def test_business_works_as_before_after_the_migration(self):
        SEED(django_apps, None)
        self.client.force_login(self.business.owner)

        self.assertTrue(get_access(self.business).can("panel.edit"))
        self.assertEqual(self.client.get(reverse("panel")).status_code, 200)
        self.assertEqual(self.client.get(reverse("service_create")).status_code, 200)
        page = self.client.get(reverse("booking_page", args=[self.business.slug]))
        self.assertNotContains(page, "todavía no está tomando reservas")
        token = self.appointment.manage_token
        detail = self.client.get(reverse("appointment_detail", args=[token]))
        self.assertContains(detail, "Turno confirmado")

    def test_pilot_exception_is_kept_with_an_explicit_grant(self):
        from io import StringIO

        from django.core.management import call_command

        SEED(django_apps, None)
        call_command("grant_plan", self.business.slug, "piloto", stdout=StringIO())

        subscription = Subscription.objects.get(business=self.business)
        self.assertEqual((subscription.status, subscription.plan.code), ("active", "piloto"))
        self.assertIsNone(subscription.current_period_end)
        self.assertEqual(Appointment.objects.filter(business=self.business).count(), 1)


class MigrationReversibilityTests(TransactionTestCase):
    """The billing migrations can be rolled back and applied again."""

    # Restore the seeded plan catalog afterwards, so later tests still find it.
    serialized_rollback = True

    def test_billing_migrations_roll_back_and_forward(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes("billing")

        executor.migrate([("billing", None)])
        executor.loader.build_graph()
        tables = connection.introspection.table_names()
        self.assertNotIn("billing_subscription", tables)
        self.assertNotIn("billing_plan", tables)
        self.assertIn("businesses_business", tables)

        executor = MigrationExecutor(connection)
        executor.migrate(latest)
        self.assertIn("billing_subscription", connection.introspection.table_names())
