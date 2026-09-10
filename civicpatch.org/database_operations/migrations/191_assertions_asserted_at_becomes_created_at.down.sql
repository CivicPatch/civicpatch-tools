-- Exactly reverses 191. A rename loses nothing, so the round trip is clean.
BEGIN;

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'assertions_created_by_fkey') THEN
        ALTER TABLE assertions RENAME CONSTRAINT assertions_created_by_fkey
            TO assertions_asserted_by_fkey;
    END IF;
END $$;

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public' AND table_name = 'assertions'
                 AND column_name = 'created_at') THEN
        ALTER TABLE assertions RENAME COLUMN created_at TO asserted_at;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public' AND table_name = 'assertions'
                 AND column_name = 'created_by') THEN
        ALTER TABLE assertions RENAME COLUMN created_by TO asserted_by;
    END IF;
END $$;

COMMIT;
