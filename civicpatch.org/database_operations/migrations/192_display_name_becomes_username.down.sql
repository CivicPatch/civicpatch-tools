-- Reverses 192's schema, not its backfill: which rows got the id-as-placeholder value and
-- which had a real, user-picked one is not recoverable once merged into one NOT NULL column.
BEGIN;

ALTER TABLE users ALTER COLUMN username DROP NOT NULL;

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_username_unique') THEN
        ALTER TABLE users RENAME CONSTRAINT users_username_unique TO users_display_name_unique;
    END IF;
END $$;

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public' AND table_name = 'users'
                 AND column_name = 'username') THEN
        ALTER TABLE users RENAME COLUMN username TO display_name;
    END IF;
END $$;

COMMIT;
