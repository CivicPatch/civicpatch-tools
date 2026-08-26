-- A term belongs to the tenure. Popolo gives Person only birth_date / death_date, and on the
-- person these cannot express one human holding two seats with two terms.
--
-- 144 backfilled `memberships`; nothing has written or read these since. `PERSON_JSON` projects
-- both off the open membership, as it already does for `office`.
BEGIN;

ALTER TABLE people DROP COLUMN IF EXISTS start_date;
ALTER TABLE people DROP COLUMN IF EXISTS end_date;

COMMIT;
