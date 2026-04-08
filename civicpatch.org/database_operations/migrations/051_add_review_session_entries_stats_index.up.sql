BEGIN;

CREATE INDEX idx_review_session_entries_stats
    ON review_session_entries (review_session_id, status, created_at DESC);

COMMIT;
