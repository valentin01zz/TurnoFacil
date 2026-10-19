"""Email verification and canonical emails.

Existing accounts predate verification: they are marked verified (from their join date) so nobody gets locked
out, and their canonical email is computed. New accounts start unverified.
"""

from django.db import migrations, models


def canonical(email):
    local, _, domain = email.strip().lower().rpartition("@")
    local = local.split("+", 1)[0]
    if domain in {"gmail.com", "googlemail.com"}:
        local = local.replace(".", "")
        domain = "gmail.com"
    return f"{local}@{domain}"


def fill(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    taken = set()
    for user in User.objects.order_by("date_joined", "pk"):
        value = canonical(user.email)
        # Two old accounts on the same mailbox keep working; the later one keeps its plain address.
        if value in taken:
            value = user.email.strip().lower()
        taken.add(value)
        user.email_canonical = value
        user.email_verified_at = user.date_joined
        user.save(update_fields=["email_canonical", "email_verified_at"])


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="email_canonical",
            field=models.CharField(max_length=254, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="email_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="verification_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(fill, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="user",
            name="email_canonical",
            field=models.CharField(max_length=254, unique=True),
        ),
    ]
