BEGIN;

CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY,
    request_id VARCHAR(255) NOT NULL,
    job_type TEXT NOT NULL, -- people
    requested_by_provider TEXT,
    requested_by_provider_user_id TEXT,
    progress INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending', -- pending, running, completed, failed, cancelled
    arguments_json JSONB,
    result_json JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jobs_requested_by
    ON jobs (requested_by_provider, requested_by_provider_user_id);

CREATE INDEX IF NOT EXISTS idx_jobs_request_id
    ON jobs (request_id);

COMMIT;