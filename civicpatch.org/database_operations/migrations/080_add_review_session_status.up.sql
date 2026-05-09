BEGIN;

ALTER TABLE review_sessions
    ADD COLUMN status TEXT NOT NULL DEFAULT 'idle',
    ADD COLUMN status_updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;

CREATE INDEX idx_review_sessions_status
    ON review_sessions (user_id, state_code, status);

COMMIT;
