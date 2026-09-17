BEGIN;

DROP INDEX IF EXISTS source_records_organization_id_idx;
ALTER TABLE source_records DROP COLUMN IF EXISTS organization_id;

COMMIT;
