-- Exactly reverses 222: `claims` -> `assertions`, with its indexes and constraints.

BEGIN;

ALTER TABLE IF EXISTS claims RENAME TO assertions;

ALTER INDEX IF EXISTS claims_pkey RENAME TO assertions_pkey;
ALTER INDEX IF EXISTS claims_changeset_id_idx RENAME TO assertions_changeset_id_idx;
ALTER INDEX IF EXISTS claims_entity_idx RENAME TO assertions_entity_idx;
ALTER INDEX IF EXISTS claims_withdraw_changeset_idx RENAME TO assertions_withdraw_changeset_idx;
ALTER INDEX IF EXISTS claims_withdrawn_by_changeset_id_idx
    RENAME TO assertions_withdrawn_by_changeset_id_idx;

DO $$
DECLARE
    old_name text;
BEGIN
    FOREACH old_name IN ARRAY ARRAY[
        'claims_entity_type_check',
        'claims_kind_check',
        'claims_sources_nonempty',
        'claims_withdraw_names_a_fact',
        'claims_withdrawn_together',
        'claims_changeset_id_fkey',
        'claims_created_by_fkey',
        'claims_withdrawn_by_changeset_id_fkey',
        'claims_withdrawn_by_fkey'
    ]
    LOOP
        IF EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = old_name AND conrelid = 'assertions'::regclass
        ) THEN
            EXECUTE format(
                'ALTER TABLE assertions RENAME CONSTRAINT %I TO %I',
                old_name,
                'assertions_' || substr(old_name, length('claims_') + 1)
            );
        END IF;
    END LOOP;
END $$;

COMMIT;
