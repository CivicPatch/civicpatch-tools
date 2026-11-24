-- The state batch that claimed a run: its Temporal run id. NULL for a run started by hand. A collector's
-- candidates leave out places this batch already tried, so a failing place is not claimed again within it,
-- and a new batch may retry it at once.

BEGIN;

ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS state_batch_id text;
CREATE INDEX IF NOT EXISTS pipeline_runs_state_batch_id_idx ON pipeline_runs (state_batch_id) WHERE state_batch_id IS NOT NULL;

COMMIT;
