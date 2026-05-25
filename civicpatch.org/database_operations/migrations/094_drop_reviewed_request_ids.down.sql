BEGIN;

ALTER TABLE review_sessions ADD COLUMN reviewed_request_ids TEXT[] NOT NULL DEFAULT '{}';

COMMIT;
