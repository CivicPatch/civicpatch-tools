BEGIN;

ALTER TABLE jurisdictions
    DROP COLUMN IF EXISTS jurisdictions_ocdid_slug;

COMMIT;
