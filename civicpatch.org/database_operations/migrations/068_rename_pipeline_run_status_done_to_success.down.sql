BEGIN;

UPDATE pipeline_runs SET status = 'DONE' WHERE status = 'SUCCESS';

COMMIT;
