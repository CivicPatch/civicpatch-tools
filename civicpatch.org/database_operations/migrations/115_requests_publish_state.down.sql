-- Exact reverse of 115. The constraint and FK go first, then the columns.
--
-- The dropped values are recoverable: `pull_requests` still holds the state these were
-- backfilled from, and nothing in 115 deleted or altered that table.
BEGIN;

ALTER TABLE requests DROP CONSTRAINT IF EXISTS requests_publish_state_check;
ALTER TABLE requests DROP CONSTRAINT IF EXISTS requests_resolved_by_user_id_fkey;

ALTER TABLE requests DROP COLUMN IF EXISTS open_data_url;
ALTER TABLE requests DROP COLUMN IF EXISTS resolved_by_user_id;
ALTER TABLE requests DROP COLUMN IF EXISTS dismissed_at;
ALTER TABLE requests DROP COLUMN IF EXISTS published_at;

COMMIT;
