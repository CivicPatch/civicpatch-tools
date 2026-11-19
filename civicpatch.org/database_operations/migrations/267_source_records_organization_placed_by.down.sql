BEGIN;

ALTER TABLE source_records DROP CONSTRAINT IF EXISTS source_records_organization_placed_by_check;
ALTER TABLE source_records DROP COLUMN IF EXISTS organization_placed_by;

COMMIT;
