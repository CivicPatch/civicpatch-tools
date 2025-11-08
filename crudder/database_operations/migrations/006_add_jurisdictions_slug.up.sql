BEGIN;

ALTER TABLE jurisdictions
    ADD COLUMN jurisdiction_ocdid_slug TEXT;

COMMIT;
