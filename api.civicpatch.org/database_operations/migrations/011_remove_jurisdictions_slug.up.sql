BEGIN;

ALTER TABLE jurisdictions
    DROP COLUMN IF EXISTS jurisdiction_ocdid_slug;

COMMIT;

