BEGIN;

DROP INDEX IF EXISTS organizations_one_default_per_jurisdiction;
ALTER TABLE organizations DROP COLUMN IF EXISTS meta_is_default;

COMMIT;
