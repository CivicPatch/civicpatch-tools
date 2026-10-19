BEGIN;

ALTER TABLE jurisdictions DROP COLUMN IF EXISTS extras_organizations;

COMMIT;
