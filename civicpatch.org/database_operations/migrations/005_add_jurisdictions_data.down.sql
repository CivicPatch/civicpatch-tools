BEGIN;

ALTER TABLE jurisdictions
    DROP COLUMN data;

COMMIT;
