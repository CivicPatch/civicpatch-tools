BEGIN;

ALTER TABLE source_records DROP COLUMN IF EXISTS other_names;

COMMIT;
