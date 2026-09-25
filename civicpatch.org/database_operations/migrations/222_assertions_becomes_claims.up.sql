-- The table is renamed, not reshaped: `assertions` -> `claims` (plan step 5b).
--
-- `RENAME TO` moves the table and nothing else, so its five indexes, five checks and four
-- foreign keys would keep announcing the old name. They are renamed here too, which is why this
-- is longer than one statement.
--
-- Idempotent throughout. `ALTER TABLE IF EXISTS` and `ALTER INDEX IF EXISTS` no-op once the
-- rename has happened; constraints have no IF EXISTS form, so each is guarded on pg_constraint.

BEGIN;

ALTER TABLE IF EXISTS assertions RENAME TO claims;

ALTER INDEX IF EXISTS assertions_pkey RENAME TO claims_pkey;
ALTER INDEX IF EXISTS assertions_changeset_id_idx RENAME TO claims_changeset_id_idx;
ALTER INDEX IF EXISTS assertions_entity_idx RENAME TO claims_entity_idx;
ALTER INDEX IF EXISTS assertions_withdraw_changeset_idx RENAME TO claims_withdraw_changeset_idx;
ALTER INDEX IF EXISTS assertions_withdrawn_by_changeset_id_idx
    RENAME TO claims_withdrawn_by_changeset_id_idx;

DO $$
DECLARE
    old_name text;
BEGIN
    FOREACH old_name IN ARRAY ARRAY[
        'assertions_entity_type_check',
        'assertions_kind_check',
        'assertions_sources_nonempty',
        'assertions_withdraw_names_a_fact',
        'assertions_withdrawn_together',
        'assertions_changeset_id_fkey',
        'assertions_created_by_fkey',
        'assertions_withdrawn_by_changeset_id_fkey',
        'assertions_withdrawn_by_fkey'
    ]
    LOOP
        IF EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = old_name AND conrelid = 'claims'::regclass
        ) THEN
            EXECUTE format(
                'ALTER TABLE claims RENAME CONSTRAINT %I TO %I',
                old_name,
                'claims_' || substr(old_name, length('assertions_') + 1)
            );
        END IF;
    END LOOP;
END $$;

COMMIT;
