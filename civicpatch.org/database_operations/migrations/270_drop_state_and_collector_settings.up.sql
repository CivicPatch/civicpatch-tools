-- Every pipeline's cadence and caps now live in pipeline_settings (269), which nothing reads these from.
-- global_settings stays: the one cap over every pipeline in every state.

BEGIN;

DROP TABLE IF EXISTS state_settings;
DROP TABLE IF EXISTS collector_settings;

COMMIT;
