BEGIN;

DROP INDEX IF EXISTS idx_review_sessions_status;

ALTER TABLE review_sessions
    DROP COLUMN IF EXISTS status,
    DROP COLUMN IF EXISTS status_updated_at;

COMMIT;
