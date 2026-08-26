-- Rebuilds the table and its rows from the columns. `id` restarts: it was a bare sequence
-- nothing referenced — `request_id` is what every other table points at.
BEGIN;

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id            serial PRIMARY KEY,
    request_id    uuid NOT NULL UNIQUE,
    progress      integer DEFAULT 0,
    status        text NOT NULL DEFAULT 'pending',
    created_at    timestamptz DEFAULT CURRENT_TIMESTAMP,
    updated_at    timestamptz DEFAULT CURRENT_TIMESTAMP,
    github_run_id bigint
);

-- `github_run_id` is not restored: the up dropped it without copying it anywhere.
INSERT INTO pipeline_runs (request_id, status, progress, created_at, updated_at)
SELECT id, COALESCE(status, 'pending'), COALESCE(progress, 0),
       created_at, COALESCE(sourced_at, created_at)
FROM requests
WHERE status IS NOT NULL
ON CONFLICT (request_id) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_jobs_request_id ON pipeline_runs (request_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs (status);

-- Lossy: the up dropped `updated_at` without copying it anywhere, because nothing read or
-- wrote it. Rows come back stamped now(), not with whatever they held.
ALTER TABLE requests ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

DROP INDEX IF EXISTS idx_requests_status;
ALTER TABLE requests DROP COLUMN IF EXISTS sourced_at;
ALTER TABLE requests DROP COLUMN IF EXISTS status;
ALTER TABLE requests DROP COLUMN IF EXISTS progress;

COMMIT;
