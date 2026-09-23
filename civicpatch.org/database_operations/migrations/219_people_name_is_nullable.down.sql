BEGIN;

-- Fails if a nameless person has been projected, which is the case this migration exists for.
ALTER TABLE people ALTER COLUMN name SET NOT NULL;

COMMIT;
