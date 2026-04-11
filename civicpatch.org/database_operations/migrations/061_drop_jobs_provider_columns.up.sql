BEGIN;
DROP INDEX idx_jobs_requested_by;
ALTER TABLE jobs
    DROP COLUMN requested_by_provider,
    DROP COLUMN requested_by_provider_user_id;
COMMIT;
