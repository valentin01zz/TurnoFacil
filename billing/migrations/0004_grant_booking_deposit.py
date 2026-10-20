"""Give the deposit by bank transfer (booking.deposit) to the Profesional and Negocio plans."""

from django.db import migrations

FEATURE = "booking.deposit"
PLANS = ["profesional", "negocio"]


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
        ("billing", "0003_checkoutattempt_providerpayment"),
    ]

    operations = [
        migrations.RunPython(grant, revoke),
    ]
