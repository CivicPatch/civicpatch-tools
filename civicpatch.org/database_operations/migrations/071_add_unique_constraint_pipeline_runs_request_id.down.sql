BEGIN;
ALTER TABLE pipeline_runs DROP CONSTRAINT pipeline_runs_request_id_unique;
COMMIT;
