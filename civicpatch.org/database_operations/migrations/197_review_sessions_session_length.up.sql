-- `review_sessions.daily_goal` becomes `session_length`: the column was never a daily
-- cadence — no reset, no streak, nothing calendar-based reads it — it is just how many
-- entries one session should include, capped by availability
-- (database/review_session_navigation.py's "Session length = the goal, capped by..."
-- already said as much). The name just never caught up to what it does.
--
-- **Idempotency**: postgres has no `IF EXISTS` for `RENAME COLUMN`, so it is guarded on
-- the catalog, same idiom as 192.
BEGIN;

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public' AND table_name = 'review_sessions'
                 AND column_name = 'daily_goal') THEN
        ALTER TABLE review_sessions RENAME COLUMN daily_goal TO session_length;
    END IF;
END $$;

COMMIT;
