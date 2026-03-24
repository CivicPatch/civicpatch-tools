BEGIN;
DROP INDEX IF EXISTS idx_review_session_entries_review_session_id;
DROP INDEX IF EXISTS idx_review_session_entries_one_viewer;
DROP TABLE IF EXISTS review_session_entries;
DROP TABLE IF EXISTS review_sessions;
COMMIT;
