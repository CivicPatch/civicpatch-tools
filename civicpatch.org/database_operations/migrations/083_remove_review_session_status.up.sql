BEGIN;

ALTER TABLE review_sessions DROP COLUMN status;
ALTER TABLE review_sessions DROP COLUMN status_updated_at;
ALTER TABLE review_sessions ADD COLUMN updated_at timestamptz NOT NULL DEFAULT NOW();

COMMIT;
