BEGIN;

ALTER TABLE jobs ALTER COLUMN request_id TYPE uuid USING request_id::uuid;

COMMIT;
