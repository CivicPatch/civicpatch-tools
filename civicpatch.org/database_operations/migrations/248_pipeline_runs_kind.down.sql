-- A collector's runs have no meaning without the column, so they go first, with their calls and
-- issues (both cascade).

BEGIN;

DELETE FROM pipeline_runs WHERE kind <> 'people_collector';
ALTER TABLE pipeline_runs DROP CONSTRAINT IF EXISTS pipeline_runs_kind_check;
ALTER TABLE pipeline_runs DROP COLUMN IF EXISTS kind;

COMMIT;
