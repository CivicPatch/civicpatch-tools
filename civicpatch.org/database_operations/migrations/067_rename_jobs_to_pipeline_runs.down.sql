BEGIN;
ALTER TABLE pipeline_runs RENAME TO jobs;
ALTER INDEX idx_pipeline_runs_status RENAME TO idx_jobs_status;
COMMIT;
