BEGIN;

DELETE FROM activity WHERE type IN ('pipeline_run_start', 'pipeline_run_end');
DELETE FROM activity_types WHERE type IN ('pipeline_run_start', 'pipeline_run_end');

COMMIT;
