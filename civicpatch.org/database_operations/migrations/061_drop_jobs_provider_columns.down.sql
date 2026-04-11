BEGIN;
ALTER TABLE jobs
    ADD COLUMN requested_by_provider text,
    ADD COLUMN requested_by_provider_user_id text;
CREATE INDEX idx_jobs_requested_by ON jobs (requested_by_provider, requested_by_provider_user_id);
COMMIT;
