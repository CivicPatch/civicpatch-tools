BEGIN;

DROP INDEX IF EXISTS idx_review_session_entries_one_viewer;

UPDATE review_session_entries SET status = 'deferred' WHERE status = 'viewing';

ALTER TABLE review_session_entries ALTER COLUMN status SET DEFAULT 'deferred';

COMMIT;
