BEGIN;

-- Dropped columns cannot be restored without a pre-migration snapshot.
RAISE EXCEPTION 'Migration 036 cannot be reversed automatically. Restore from a pre-migration snapshot.';

COMMIT;
