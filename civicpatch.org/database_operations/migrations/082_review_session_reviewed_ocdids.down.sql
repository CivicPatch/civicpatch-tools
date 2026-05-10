BEGIN;

DROP INDEX IF EXISTS idx_review_session_entries_active_claim;
ALTER TABLE review_sessions DROP COLUMN IF EXISTS reviewed_ocdids;

COMMIT;
