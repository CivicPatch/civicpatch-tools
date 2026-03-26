BEGIN;

ALTER TABLE pull_requests
  ADD COLUMN resolved_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL;

COMMIT;
