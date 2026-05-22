BEGIN;

ALTER TABLE users DROP COLUMN last_login_at;

COMMIT;
