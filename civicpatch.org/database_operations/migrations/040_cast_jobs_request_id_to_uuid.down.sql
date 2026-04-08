BEGIN;

ALTER TABLE jobs ALTER COLUMN request_id TYPE character varying USING request_id::text;

COMMIT;
