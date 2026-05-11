BEGIN;

ALTER TABLE review_sessions DROP COLUMN updated_at;
ALTER TABLE review_sessions ADD COLUMN status text NOT NULL DEFAULT 'idle';
ALTER TABLE review_sessions ADD COLUMN status_updated_at timestamptz;

COMMIT;
