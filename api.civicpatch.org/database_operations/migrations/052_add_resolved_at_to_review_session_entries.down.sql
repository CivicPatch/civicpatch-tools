BEGIN;

ALTER TABLE review_session_entries
    DROP COLUMN resolved_at;

COMMIT;
