BEGIN;

ALTER TABLE review_sessions ADD COLUMN ended_at TIMESTAMPTZ NULL;

ALTER TABLE review_sessions DROP CONSTRAINT review_sessions_user_state_unique;

CREATE UNIQUE INDEX review_sessions_user_state_active_unique
    ON review_sessions (user_id, state_code)
    WHERE ended_at IS NULL;

COMMIT;
