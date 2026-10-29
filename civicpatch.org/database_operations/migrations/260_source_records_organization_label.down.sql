BEGIN;

ALTER TABLE source_records DROP COLUMN IF EXISTS organization_label;

COMMIT;
