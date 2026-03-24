BEGIN;

ALTER TABLE review_session_entries ADD COLUMN entry_number INTEGER;

COMMIT;
