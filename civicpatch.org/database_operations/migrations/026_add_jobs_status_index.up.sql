BEGIN;

CREATE INDEX idx_jobs_status ON jobs (status);

COMMIT;
