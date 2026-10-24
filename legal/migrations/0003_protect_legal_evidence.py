"""The database itself refuses to change legal evidence, whatever path the change takes.

Model methods already refuse it, but bulk operations (QuerySet.update or .delete) skip them. These
triggers cover every path short of dropping them. Published documents can never be updated or
deleted. Acceptances can never be updated, but can be deleted: deleting an account (a data deletion
request) deletes its acceptances too. TRUNCATE, used only by test teardown, is not covered.
"""

from django.db import migrations

FORWARD = """
CREATE FUNCTION legal_refuse_change() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'legal evidence in % cannot be changed (%)', TG_TABLE_NAME, TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER legal_document_immutable
    BEFORE UPDATE OR DELETE ON legal_legaldocument
    FOR EACH ROW EXECUTE FUNCTION legal_refuse_change();

CREATE TRIGGER legal_acceptance_immutable
    BEFORE UPDATE ON legal_legalacceptance
    FOR EACH ROW EXECUTE FUNCTION legal_refuse_change();
"""

BACKWARD = """
DROP TRIGGER IF EXISTS legal_acceptance_immutable ON legal_legalacceptance;
DROP TRIGGER IF EXISTS legal_document_immutable ON legal_legaldocument;
DROP FUNCTION IF EXISTS legal_refuse_change();
"""


class Migration(migrations.Migration):
    dependencies = [("legal", "0002_service_request_tracking")]

    operations = [migrations.RunSQL(FORWARD, BACKWARD)]
