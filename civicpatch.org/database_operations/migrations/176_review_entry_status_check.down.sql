BEGIN;

ALTER TABLE review_session_entries DROP CONSTRAINT IF EXISTS review_session_entries_status_check;

COMMIT;
