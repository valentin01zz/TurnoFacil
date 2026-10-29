"""Give the income and reports panel (reports) to Profesional, Negocio and the free pilot plan
(Founder decision, 2026-10-28). The trial runs on Profesional, so trial businesses get it too."""

from django.db import migrations

FEATURE = "reports"
PLANS = ["profesional", "negocio", "piloto"]


def grant(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    for plan in Plan.objects.filter(code__in=PLANS):
        if FEATURE not in plan.features:
            plan.features = [*plan.features, FEATURE]
            plan.save(update_fields=["features"])


def revoke(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    for plan in Plan.objects.all():
        if FEATURE in plan.features:
            plan.features = [code for code in plan.features if code != FEATURE]
            plan.save(update_fields=["features"])


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0004_grant_booking_deposit"),
    ]

    operations = [
        migrations.RunPython(grant, revoke),
    ]
