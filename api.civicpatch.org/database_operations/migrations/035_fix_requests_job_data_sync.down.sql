BEGIN;

-- Reverting this migration would mean re-introducing the incorrect links from 034.
-- There is no safe mechanical reversal — rolling back requires restoring from a
-- pre-035 database snapshot.
RAISE EXCEPTION 'Migration 035 cannot be reversed automatically. Restore from a pre-migration snapshot.';

COMMIT;
