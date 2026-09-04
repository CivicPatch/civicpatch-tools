-- The column is generated, so nothing is lost: dropping it discards no fact the other columns
-- do not still hold.

BEGIN;

DROP INDEX IF EXISTS changesets_state_idx;
ALTER TABLE changesets DROP COLUMN IF EXISTS state;

COMMIT;
