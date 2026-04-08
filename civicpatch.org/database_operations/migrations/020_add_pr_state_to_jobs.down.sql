BEGIN;

DROP INDEX IF EXISTS idx_jobs_pull_request_status;
DROP INDEX IF EXISTS idx_jobs_jurisdiction_ocdid;

ALTER TABLE jobs
    DROP COLUMN IF EXISTS pull_request_status,
    DROP COLUMN IF EXISTS pull_request_merged_at;

COMMIT;
