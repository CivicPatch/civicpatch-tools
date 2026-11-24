BEGIN;

DROP INDEX IF EXISTS pipeline_runs_state_batch_id_idx;
ALTER TABLE pipeline_runs DROP COLUMN IF EXISTS state_batch_id;

COMMIT;
