BEGIN;
ALTER TABLE jobs RENAME TO pipeline_runs;
ALTER INDEX idx_jobs_status RENAME TO idx_pipeline_runs_status;
COMMIT;
