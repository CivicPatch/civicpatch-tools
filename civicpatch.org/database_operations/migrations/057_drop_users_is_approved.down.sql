BEGIN;
ALTER TABLE users ADD COLUMN is_approved boolean DEFAULT false;
COMMIT;
