BEGIN;

ALTER TABLE pipeline_runs DROP COLUMN IF EXISTS pipeline_run_cap_usd;

COMMIT;
