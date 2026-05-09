BEGIN;

ALTER TABLE review_sessions DROP COLUMN IF EXISTS current_entry_number;

COMMIT;
