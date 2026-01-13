BEGIN;

DROP INDEX IF EXISTS idx_jobs_requested_by;
DROP INDEX IF EXISTS idx_jobs_request_id;
DROP TABLE IF EXISTS jobs;

COMMIT;
