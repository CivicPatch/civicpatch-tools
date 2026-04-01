BEGIN;

ALTER TABLE review_session_entries
    ADD COLUMN resolved_at TIMESTAMPTZ;

COMMIT;
