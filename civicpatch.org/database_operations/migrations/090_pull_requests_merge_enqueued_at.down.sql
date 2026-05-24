BEGIN;

ALTER TABLE pull_requests DROP COLUMN IF EXISTS merge_enqueued_at;

COMMIT;
