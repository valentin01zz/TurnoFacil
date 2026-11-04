"""Acceptances can only be deleted together with their account, through `delete_business`.

0003 allowed any delete of acceptances so account deletion could cascade. Now the trigger also
refuses deletes unless the transaction set `legal.allow_evidence_delete` to "on", which only
`legal.data.delete_business` does (SET LOCAL: it ends with that transaction).
"""

from django.db import migrations

FORWARD = """
CREATE FUNCTION legal_guard_acceptance() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE'
       AND coalesce(current_setting('legal.allow_evidence_delete', true), '') = 'on' THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'legal evidence in % cannot be changed (%)', TG_TABLE_NAME, TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER legal_acceptance_immutable ON legal_legalacceptance;
CREATE TRIGGER legal_acceptance_immutable
    BEFORE UPDATE OR DELETE ON legal_legalacceptance
    FOR EACH ROW EXECUTE FUNCTION legal_guard_acceptance();
"""

BACKWARD = """
DROP TRIGGER legal_acceptance_immutable ON legal_legalacceptance;
CREATE TRIGGER legal_acceptance_immutable
    BEFORE UPDATE ON legal_legalacceptance
    FOR EACH ROW EXECUTE FUNCTION legal_refuse_change();
DROP FUNCTION legal_guard_acceptance();
"""


class Migration(migrations.Migration):
    dependencies = [("legal", "0004_operator_notice_tracking")]

    operations = [migrations.RunSQL(FORWARD, BACKWARD)]
