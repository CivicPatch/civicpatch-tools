BEGIN;

UPDATE jobs SET status = 'COMPLETED' WHERE status = 'DONE';

COMMIT;
