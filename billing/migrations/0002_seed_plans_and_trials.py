"""Seed the plan catalog and give every existing business its trial (ADR-0004)."""

from datetime import timedelta
from decimal import Decimal

from django.db import migrations
from django.utils import timezone

ALL_FEATURES = [
    "booking.online",
    "booking.emails",
    "booking.self_service",
    "panel.edit",
    "agenda.chart",
]

PLANS = [
    ("esencial", "Esencial", Decimal("14900"), 1, True, 1),
    ("profesional", "Profesional", Decimal("24900"), 5, True, 2),
    ("negocio", "Negocio", Decimal("39900"), 15, True, 3),
    # Free plan for the pilot business, granted by an operator with `grant_plan`. Not shown to owners.
    ("piloto", "Piloto", Decimal("0"), 15, False, 9),
]

TRIAL_DAYS = 14


def seed(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    Subscription = apps.get_model("billing", "Subscription")
    SubscriptionEvent = apps.get_model("billing", "SubscriptionEvent")
    Business = apps.get_model("businesses", "Business")

    for code, name, price, max_professionals, is_public, order in PLANS:
        Plan.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "monthly_price": price,
                "currency": "ARS",
                "max_professionals": max_professionals,
                "features": ALL_FEATURES,
                "is_public": is_public,
                "sort_order": order,
            },
        )

    trial_plan = Plan.objects.get(code="profesional")
    now = timezone.now()
    for business in Business.objects.filter(subscription__isnull=True):
        subscription = Subscription.objects.create(
            business=business,
            plan=trial_plan,
            status="trialing",
            trial_started_at=now,
            trial_ends_at=now + timedelta(days=TRIAL_DAYS),
        )
        SubscriptionEvent.objects.create(
            subscription=subscription,
            to_status="trialing",
            reason="Prueba iniciada al incorporar planes (negocio existente)",
        )


def unseed(apps, schema_editor):
    apps.get_model("billing", "Subscription").objects.all().delete()
    apps.get_model("billing", "Plan").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0001_initial"),
        ("businesses", "0004_business_address_alter_business_name"),
    ]

    operations = [migrations.RunPython(seed, unseed)]
