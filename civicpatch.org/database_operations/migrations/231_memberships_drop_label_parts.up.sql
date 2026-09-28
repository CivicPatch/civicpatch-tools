-- The membership label is derived (10a): designations and unmatched text are parsed from the page's
-- words on every fold and rendered into `label`, so nothing reads them as columns any more.

BEGIN;

ALTER TABLE memberships DROP COLUMN IF EXISTS designations;
ALTER TABLE memberships DROP COLUMN IF EXISTS meta_unmatched_text;

COMMIT;
