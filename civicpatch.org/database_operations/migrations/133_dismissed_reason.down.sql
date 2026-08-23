BEGIN;

ALTER TABLE requests DROP COLUMN dismissed_reason;

COMMIT;
