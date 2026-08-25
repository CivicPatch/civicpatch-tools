BEGIN;

-- Structure only. The rosters are not recoverable and nothing writes this column any more;
-- this exists so the migration round-trips.
ALTER TABLE requests ADD COLUMN IF NOT EXISTS data_json jsonb;

COMMIT;
