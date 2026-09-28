-- Exactly reverses 233.

BEGIN;

ALTER TABLE changesets ALTER COLUMN jurisdiction_ocdid DROP NOT NULL;

COMMIT;
