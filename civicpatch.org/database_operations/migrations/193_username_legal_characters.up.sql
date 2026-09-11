-- 192 backfilled a username for every row but put no restriction on what one could contain —
-- the application only started rejecting spaces and other characters after that, so any
-- username entered before then (direct-assert `display_name`s predate any character rule at
-- all) can be sitting on a value the app itself would now refuse to accept.
--
-- Reset to the id-as-placeholder convention 192 already established, rather than sanitizing
-- the existing value: a partial character strip risks two different illegal names colliding
-- on the same sanitized result, where the placeholder is always legal and always unique
-- because it always was.
BEGIN;

UPDATE users
SET username = id::text
WHERE username !~ '^[A-Za-z0-9._-]+$' OR char_length(username) > 50;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_username_legal_chars') THEN
        ALTER TABLE users ADD CONSTRAINT users_username_legal_chars
            CHECK (username ~ '^[A-Za-z0-9._-]+$' AND char_length(username) <= 50);
    END IF;
END $$;

COMMIT;
