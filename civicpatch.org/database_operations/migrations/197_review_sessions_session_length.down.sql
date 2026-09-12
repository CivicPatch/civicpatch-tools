-- Reverses 197's rename.
BEGIN;

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public' AND table_name = 'review_sessions'
                 AND column_name = 'session_length') THEN
        ALTER TABLE review_sessions RENAME COLUMN session_length TO daily_goal;
    END IF;
END $$;

COMMIT;
