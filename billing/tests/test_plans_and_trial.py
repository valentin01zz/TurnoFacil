from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.apps import apps as django_apps
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from billing.access import days_left, get_access
from billing.catalog import ALL_FEATURES, BOOKING_ONLINE, PANEL_EDIT
from billing.models import Plan, Subscription, SubscriptionEvent
from billing.services import start_trial
from bookings.tests.helpers import create_business

from .helpers import end_trial


class CatalogTests(TestCase):
    def test_public_plans_with_reference_prices_and_limits(self):
        plans = {p.code: p for p in Plan.objects.filter(is_public=True)}

        self.assertEqual(list(plans), ["esencial", "profesional", "negocio"])
        self.assertEqual(plans["esencial"].monthly_price, Decimal("14900"))
        self.assertEqual(plans["profesional"].monthly_price, Decimal("24900"))
        self.assertEqual(plans["negocio"].monthly_price, Decimal("39900"))
        self.assertEqual([p.max_professionals for p in plans.values()], [1, 5, 15])
        self.assertTrue(all(p.currency == "ARS" for p in plans.values()))
        self.assertTrue(all(set(p.features) == set(ALL_FEATURES) for p in plans.values()))

    def test_pilot_plan_is_free_and_hidden(self):
        pilot = Plan.objects.get(code="piloto")

        self.assertFalse(pilot.is_public)
        self.assertEqual(pilot.monthly_price, 0)

    def test_set_plan_changes_price_and_limit_without_code(self):
        out = StringIO()

        call_command(
            "set_plan", "esencial", "--price", "15900", "--max-professionals", "2", stdout=out
        )

        plan = Plan.objects.get(code="esencial")
        self.assertEqual(plan.monthly_price, Decimal("15900"))
        self.assertEqual(plan.max_professionals, 2)
        self.assertIn("hasta 2 profesionales", out.getvalue())

    def test_set_plan_rejects_bad_values(self):
        for args in (
            ["noexiste"],
            ["esencial", "--price", "caro"],
            ["esencial", "--price", "-1"],
            ["esencial", "--max-professionals", "0"],
        ):
            with self.assertRaises(CommandError, msg=args):
                call_command("set_plan", *args, stdout=StringIO())


class TrialTests(TestCase):
    def test_signup_starts_a_14_day_trial_on_the_professional_plan(self):
        before = timezone.now()
        self.client.post(
            reverse("signup"),
            {
                "business_name": "Estética Luna",
                "email": "a@example.com",
                "password": "correct-horse-battery",
            },
        )

        subscription = Subscription.objects.get(business__owner__email="a@example.com")
        self.assertEqual(subscription.status, Subscription.TRIALING)
        self.assertEqual(subscription.plan.code, "profesional")
        self.assertGreaterEqual(subscription.trial_started_at, before)
        self.assertEqual(
            subscription.trial_ends_at - subscription.trial_started_at, timedelta(days=14)
        )
        self.assertEqual(subscription.events.get().to_status, Subscription.TRIALING)

    @override_settings(TRIAL_DAYS=7)
    def test_trial_length_is_configurable(self):
        business = create_business()

        subscription = business.subscription
        self.assertEqual(
            subscription.trial_ends_at - subscription.trial_started_at, timedelta(days=7)
        )

    def test_trial_cannot_be_restarted(self):
        business = create_business()
        original = business.subscription.trial_ends_at
        end_trial(business)

        again = start_trial(business)

        self.assertLess(again.trial_ends_at, timezone.now())
        self.assertNotEqual(again.trial_ends_at, original)
        self.assertEqual(Subscription.objects.filter(business=business).count(), 1)

    def test_trial_grants_professional_access_and_days_left(self):
        business = create_business()

        access = get_access(business)

        self.assertTrue(access.in_trial)
        self.assertEqual(access.plan.code, "profesional")
        self.assertTrue(access.can(PANEL_EDIT))
        self.assertTrue(access.can(BOOKING_ONLINE))
        self.assertEqual(access.trial_days_left, 14)
        self.assertEqual(access.max_professionals, 5)

    def test_days_left_counts_partial_days(self):
        now = timezone.now()

        self.assertEqual(days_left(now + timedelta(days=2, hours=1), now), 3)
        self.assertEqual(days_left(now + timedelta(hours=3), now), 1)
        self.assertEqual(days_left(now - timedelta(hours=3), now), 0)

    def test_existing_businesses_get_a_trial_from_the_migration(self):
        business = create_business()
        Subscription.objects.filter(business=business).delete()
        seed = __import__("billing.migrations.0002_seed_plans_and_trials", fromlist=["seed"]).seed

        seed(django_apps, None)

        subscription = Subscription.objects.get(business=business)
        self.assertEqual(subscription.status, Subscription.TRIALING)
        self.assertEqual(
            subscription.trial_ends_at - subscription.trial_started_at, timedelta(days=14)
        )
        self.assertIn(
            "negocio existente", SubscriptionEvent.objects.get(subscription=subscription).reason
        )

    def test_panel_shows_days_left_and_end_date(self):
        business = create_business()
        self.client.force_login(business.owner)

        response = self.client.get(reverse("panel"))

        self.assertContains(response, "Prueba gratis: te quedan")
        self.assertContains(response, "14 días")
        end = timezone.localtime(business.subscription.trial_ends_at)
        self.assertContains(response, f"termina el {end.day} de")


class GrantPlanTests(TestCase):
    def test_operator_grants_the_free_pilot_plan(self):
        business = create_business()

        call_command("grant_plan", business.slug, "piloto", stdout=StringIO())

        access = get_access(business, now=timezone.now() + timedelta(days=400))
        self.assertEqual(access.status, Subscription.ACTIVE)
        self.assertEqual(access.plan.code, "piloto")
        self.assertEqual(access.max_professionals, 15)

    def test_grant_needs_existing_business_and_plan(self):
        with self.assertRaises(CommandError):
            call_command("grant_plan", "no-existe", "piloto", stdout=StringIO())

    def test_users_cannot_reach_hidden_plans(self):
        business = create_business()
        self.client.force_login(business.owner)

        response = self.client.post(reverse("choose_plan", args=["piloto"]))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(Subscription.objects.get(business=business).status, Subscription.TRIALING)


class NoUserCountTests(TestCase):
    def test_every_business_has_exactly_one_subscription(self):
        create_business("a@example.com", "Uno")
        create_business("b@example.com", "Dos")

        self.assertEqual(Subscription.objects.count(), User.objects.count())


class GrantPlanOptionsTests(TestCase):
    def test_months_sets_the_period_end(self):
        business = create_business()
        out = StringIO()

        call_command("grant_plan", business.slug, "esencial", "--months", "1", stdout=out)

        subscription = Subscription.objects.get(business=business)
        days = (subscription.current_period_end - timezone.now()).days
        self.assertIn(days, range(27, 32))
        self.assertIn("hasta el", out.getvalue())
        self.assertTrue(get_access(business, now=timezone.now() + timedelta(days=40)).read_only)

    def test_refuses_a_plan_below_the_active_professionals(self):
        from bookings.tests.helpers import create_professional

        business = create_business()
        create_professional(business, name="Ana", ranges=())
        create_professional(business, name="Bruno", ranges=())

        with self.assertRaises(CommandError):
            call_command("grant_plan", business.slug, "esencial", stdout=StringIO())
        self.assertEqual(Subscription.objects.get(business=business).status, "trialing")

    def test_add_months_clamps_the_day(self):
        from datetime import datetime

        from billing.management.commands.grant_plan import add_months

        self.assertEqual(add_months(datetime(2027, 1, 31), 1), datetime(2027, 2, 28))
        self.assertEqual(add_months(datetime(2026, 11, 15), 3), datetime(2027, 2, 15))
