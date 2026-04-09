BEGIN;

UPDATE jobs SET status = 'DONE' WHERE status = 'COMPLETED';

COMMIT;
