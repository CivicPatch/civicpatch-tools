-- Reverses the constraint, not the backfill: which rows were reset from an illegal value and
-- what that value was is not recoverable once overwritten.
BEGIN;

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_username_legal_chars') THEN
        ALTER TABLE users DROP CONSTRAINT users_username_legal_chars;
    END IF;
END $$;

COMMIT;
