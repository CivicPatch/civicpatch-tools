BEGIN;
ALTER TABLE users ADD COLUMN server_url text;
COMMIT;
