from django.db import migrations


def delete_exact_duplicates(apps, schema_editor):
    """Keep the oldest of identical working hours so the constraint (0006) can be created."""
    WorkingHours = apps.get_model('businesses', 'WorkingHours')
    seen = set()
    for hours in WorkingHours.objects.order_by('pk'):
        key = (hours.professional_id, hours.weekday, hours.start_time, hours.end_time)
        if key in seen:
            hours.delete()
        else:
            seen.add(key)


class Migration(migrations.Migration):
    """Data only: PostgreSQL cannot alter a table with pending trigger events in one transaction."""

    dependencies = [
        ('businesses', '0004_business_address_alter_business_name'),
    ]

    operations = [
        migrations.RunPython(delete_exact_duplicates, migrations.RunPython.noop),
    ]
