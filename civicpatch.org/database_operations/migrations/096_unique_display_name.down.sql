BEGIN;

ALTER TABLE users DROP CONSTRAINT users_display_name_unique;

COMMIT;
