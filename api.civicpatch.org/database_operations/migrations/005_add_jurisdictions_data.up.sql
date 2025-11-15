BEGIN;

ALTER TABLE jurisdictions
    ADD COLUMN data JSONB;

COMMIT;
