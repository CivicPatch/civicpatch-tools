BEGIN;

-- Structure only. The summaries are not recoverable and nothing writes this column any more;
-- this exists so the migration round-trips.
ALTER TABLE requests ADD COLUMN IF NOT EXISTS review_json jsonb;

COMMIT;
