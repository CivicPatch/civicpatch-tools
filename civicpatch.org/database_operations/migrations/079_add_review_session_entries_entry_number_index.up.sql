BEGIN;

CREATE INDEX idx_review_session_entries_entry_number
    ON review_session_entries (review_session_id, entry_number);

COMMIT;
