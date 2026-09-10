BEGIN;

DROP INDEX IF EXISTS assertions_withdrawn_by_changeset_id_idx;
DROP INDEX IF EXISTS assertions_changeset_id_idx;

ALTER TABLE assertions
    DROP COLUMN IF EXISTS withdrawn_by_changeset_id,
    DROP COLUMN IF EXISTS changeset_id;

COMMIT;
