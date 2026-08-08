BEGIN;

DROP INDEX IF EXISTS jurisdictions_parent_ocdids_idx;

ALTER TABLE jurisdictions DROP COLUMN IF EXISTS parent_ocdids;

COMMIT;
