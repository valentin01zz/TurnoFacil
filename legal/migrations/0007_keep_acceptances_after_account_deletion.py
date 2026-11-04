"""Acceptances outlive the account they belong to.

Until now deleting an account (`delete_business`) deleted its acceptances, so a business could not
be shown what it had accepted once its account was gone. Now:
- every acceptance keeps the SHA-256 of the canonical email that accepted (rows already there are
  filled in here);
- deleting the account detaches them (`user` becomes NULL) instead of deleting them;
- the trigger allows exactly that detach, and only when the transaction set
  `legal.allow_evidence_detach` to "on", which only `legal.data.delete_business` does. Any other
  update, and every delete, is refused.
"""

import hashlib

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

from accounts.identity import canonical_email

# Used only while this migration fills in the fingerprint of rows that already exist.
ALLOW_BACKFILL = """
CREATE OR REPLACE FUNCTION legal_guard_acceptance() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'UPDATE'
       AND coalesce(current_setting('legal.allow_evidence_backfill', true), '') = 'on'
       AND OLD.subject_email_sha256 = ''
       AND NEW.id = OLD.id
       AND NEW.user_id IS NOT DISTINCT FROM OLD.user_id
       AND NEW.document_id = OLD.document_id
       AND NEW.action = OLD.action
       AND NEW.context = OLD.context
       AND NEW.created_at = OLD.created_at THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'legal evidence in % cannot be changed (%)', TG_TABLE_NAME, TG_OP;
END;
$$ LANGUAGE plpgsql;
"""

ALLOW_DETACH = """
CREATE OR REPLACE FUNCTION legal_guard_acceptance() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'UPDATE'
       AND coalesce(current_setting('legal.allow_evidence_detach', true), '') = 'on'
       AND OLD.user_id IS NOT NULL
       AND NEW.user_id IS NULL
       AND NEW.id = OLD.id
       AND NEW.subject_email_sha256 = OLD.subject_email_sha256
       AND NEW.document_id = OLD.document_id
       AND NEW.action = OLD.action
       AND NEW.context = OLD.context
       AND NEW.created_at = OLD.created_at THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'legal evidence in % cannot be changed (%)', TG_TABLE_NAME, TG_OP;
END;
$$ LANGUAGE plpgsql;
"""

# The 0005 behaviour: deletes allowed with `legal.allow_evidence_delete`, never updates.
ALLOW_DELETE = """
CREATE OR REPLACE FUNCTION legal_guard_acceptance() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE'
       AND coalesce(current_setting('legal.allow_evidence_delete', true), '') = 'on' THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'legal evidence in % cannot be changed (%)', TG_TABLE_NAME, TG_OP;
END;
$$ LANGUAGE plpgsql;
"""


def fill_fingerprints(apps, schema_editor):
    LegalAcceptance = apps.get_model("legal", "LegalAcceptance")
    rows = LegalAcceptance.objects.filter(subject_email_sha256="", user__isnull=False)
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SET LOCAL legal.allow_evidence_backfill = 'on'")
        for pk, email in rows.values_list("pk", "user__email"):
            fingerprint = hashlib.sha256(canonical_email(email).encode()).hexdigest()
            cursor.execute(
                "UPDATE legal_legalacceptance SET subject_email_sha256 = %s WHERE id = %s",
                [fingerprint, pk],
            )
        cursor.execute("SET LOCAL legal.allow_evidence_backfill = 'off'")


class Migration(migrations.Migration):
    dependencies = [
        ("legal", "0006_data_deletion_requests"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="legalacceptance",
            name="subject_email_sha256",
            field=models.CharField(default="", editable=False, max_length=64),
        ),
        migrations.RunSQL(ALLOW_BACKFILL, ALLOW_DELETE),
        migrations.RunPython(fill_fingerprints, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="legalacceptance",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="legal_acceptances",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunSQL(ALLOW_DETACH, ALLOW_BACKFILL),
    ]
