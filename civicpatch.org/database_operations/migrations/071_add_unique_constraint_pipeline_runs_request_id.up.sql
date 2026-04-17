BEGIN;
ALTER TABLE pipeline_runs ADD CONSTRAINT pipeline_runs_request_id_unique UNIQUE (request_id);
COMMIT;
