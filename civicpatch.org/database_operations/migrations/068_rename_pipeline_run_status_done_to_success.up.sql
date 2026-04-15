BEGIN;

UPDATE pipeline_runs SET status = 'SUCCESS' WHERE status = 'DONE';

COMMIT;
