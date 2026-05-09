BEGIN;

ALTER TABLE review_sessions ADD COLUMN current_entry_number INTEGER NOT NULL DEFAULT 1;

COMMIT;
