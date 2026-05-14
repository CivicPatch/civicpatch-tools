BEGIN;

DROP INDEX IF EXISTS idx_jurisdictions_level;

ALTER TABLE jurisdictions DROP COLUMN IF EXISTS level;

COMMIT;
