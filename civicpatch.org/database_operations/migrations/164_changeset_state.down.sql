-- The column is generated, so nothing is lost: dropping it discards no fact the other columns
-- do not still hold.

BEGIN;

ALTER TABLE changesets DROP COLUMN IF EXISTS state;

COMMIT;
