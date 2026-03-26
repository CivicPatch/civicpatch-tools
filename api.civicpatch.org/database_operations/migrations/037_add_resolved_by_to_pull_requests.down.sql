BEGIN;

ALTER TABLE pull_requests
  DROP COLUMN IF EXISTS resolved_by_user_id;

COMMIT;
