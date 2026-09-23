BEGIN;

-- Section 2 replaced every post's random id and those ids are recorded nowhere, so this cannot
-- be reversed. The other three sections could be, but they ship with it.
DO $$ BEGIN
    RAISE EXCEPTION 'Migration 217 cannot be reversed automatically. Restore from a pre-migration snapshot.';
END $$;

COMMIT;
