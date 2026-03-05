from django.db import migrations


FORWARD_SQL = """
CREATE OR REPLACE FUNCTION flexx_enforce_user_client_has_contract()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.role = 'client' AND COALESCE(NEW.is_active, FALSE) THEN
        IF NOT EXISTS (
            SELECT 1
            FROM contracts c
            WHERE c.client_id = NEW.id
        ) THEN
            RAISE EXCEPTION
                'Active client user % must have at least one contract',
                NEW.id
                USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_flexx_user_client_requires_contract ON app_users_flexxuser;
CREATE CONSTRAINT TRIGGER trg_flexx_user_client_requires_contract
AFTER INSERT OR UPDATE OF role, is_active ON app_users_flexxuser
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION flexx_enforce_user_client_has_contract();

CREATE OR REPLACE FUNCTION flexx_enforce_contract_change_keeps_client_valid()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' OR (TG_OP = 'UPDATE' AND OLD.client_id IS DISTINCT FROM NEW.client_id) THEN
        IF EXISTS (
            SELECT 1
            FROM app_users_flexxuser u
            WHERE u.id = OLD.client_id
              AND u.role = 'client'
              AND COALESCE(u.is_active, FALSE)
        ) AND NOT EXISTS (
            SELECT 1
            FROM contracts c
            WHERE c.client_id = OLD.client_id
        ) THEN
            RAISE EXCEPTION
                'Active client user % must have at least one contract',
                OLD.client_id
                USING ERRCODE = '23514';
        END IF;
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$;

DROP TRIGGER IF EXISTS trg_flexx_contract_change_keeps_client_valid ON contracts;
CREATE CONSTRAINT TRIGGER trg_flexx_contract_change_keeps_client_valid
AFTER DELETE OR UPDATE OF client_id ON contracts
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION flexx_enforce_contract_change_keeps_client_valid();
"""


REVERSE_SQL = """
CREATE OR REPLACE FUNCTION flexx_enforce_user_client_has_contract()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.role = 'client' THEN
        IF NOT EXISTS (
            SELECT 1
            FROM contracts c
            WHERE c.client_id = NEW.id
        ) THEN
            RAISE EXCEPTION
                'Client user % must have at least one contract',
                NEW.id
                USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_flexx_user_client_requires_contract ON app_users_flexxuser;
CREATE CONSTRAINT TRIGGER trg_flexx_user_client_requires_contract
AFTER INSERT OR UPDATE OF role ON app_users_flexxuser
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION flexx_enforce_user_client_has_contract();

CREATE OR REPLACE FUNCTION flexx_enforce_contract_change_keeps_client_valid()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' OR (TG_OP = 'UPDATE' AND OLD.client_id IS DISTINCT FROM NEW.client_id) THEN
        IF EXISTS (
            SELECT 1
            FROM app_users_flexxuser u
            WHERE u.id = OLD.client_id
              AND u.role = 'client'
        ) AND NOT EXISTS (
            SELECT 1
            FROM contracts c
            WHERE c.client_id = OLD.client_id
        ) THEN
            RAISE EXCEPTION
                'Client user % must have at least one contract',
                OLD.client_id
                USING ERRCODE = '23514';
        END IF;
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$;

DROP TRIGGER IF EXISTS trg_flexx_contract_change_keeps_client_valid ON contracts;
CREATE CONSTRAINT TRIGGER trg_flexx_contract_change_keeps_client_valid
AFTER DELETE OR UPDATE OF client_id ON contracts
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION flexx_enforce_contract_change_keeps_client_valid();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("flexx", "0023_bondissue_documents_sent_other_bondissue_isin_wkn_and_more"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
