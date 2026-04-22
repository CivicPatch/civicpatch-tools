BEGIN;

CREATE INDEX IF NOT EXISTS idx_review_sessions_state_code ON review_sessions (state_code);

COMMIT;
