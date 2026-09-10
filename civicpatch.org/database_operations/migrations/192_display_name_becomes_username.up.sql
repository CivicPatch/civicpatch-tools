-- `users.display_name` becomes `users.username`: a rename, plus closing the gap the old
-- column left open. `display_name` was nullable (096) so a user could exist before ever
-- picking one; `username` is the identity every user-facing surface already falls back to
-- displaying (a fetched, unique handle beats a raw uuid), so it should always have a value.
-- Users who never picked one get their own id as a placeholder username, same shape as
-- every other value in the column, not a NULL special case.
--
-- **Idempotency**: postgres has no `IF EXISTS` for `RENAME COLUMN` or `RENAME CONSTRAINT`, so
-- both are guarded on the catalog, same idiom as 152/190/191. The backfill `UPDATE` and the
-- `SET NOT NULL` are naturally idempotent — rerunning either against an already-migrated
-- table is a no-op.
BEGIN;

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public' AND table_name = 'users'
                 AND column_name = 'display_name') THEN
        ALTER TABLE users RENAME COLUMN display_name TO username;
    END IF;
END $$;

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_display_name_unique') THEN
        ALTER TABLE users RENAME CONSTRAINT users_display_name_unique TO users_username_unique;
    END IF;
END $$;

UPDATE users SET username = id::text WHERE username IS NULL;

ALTER TABLE users ALTER COLUMN username SET NOT NULL;

COMMIT;
