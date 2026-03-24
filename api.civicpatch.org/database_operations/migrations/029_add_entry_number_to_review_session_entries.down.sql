BEGIN;

ALTER TABLE review_session_entries DROP COLUMN entry_number;

COMMIT;
