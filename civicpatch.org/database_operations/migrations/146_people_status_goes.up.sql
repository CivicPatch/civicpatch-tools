-- `status` was a cache of "has an open membership", set by PERSON_UPSERT and cleared by whoever
-- noticed an absence. Measured before removing: `inactive` matched "no open membership" for 48
-- of 48, and `active` for 20,644 of 20,664 — the 20 being three jurisdictions migration 118's
-- backfill never reached.
--
-- Every reader moved to `IS_ON_THE_ROSTER`, which asks memberships directly.
BEGIN;

ALTER TABLE people DROP CONSTRAINT IF EXISTS people_status_check;
ALTER TABLE people DROP COLUMN IF EXISTS status;

COMMIT;
