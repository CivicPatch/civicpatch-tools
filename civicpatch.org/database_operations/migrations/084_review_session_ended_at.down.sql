BEGIN;

DROP INDEX IF EXISTS review_sessions_user_state_active_unique;

ALTER TABLE review_sessions
    ADD CONSTRAINT review_sessions_user_state_unique
    UNIQUE (user_id, state_code);

ALTER TABLE review_sessions DROP COLUMN IF EXISTS ended_at;

COMMIT;
