BEGIN;

ALTER TABLE pull_requests ADD COLUMN review_state text;

COMMIT;
