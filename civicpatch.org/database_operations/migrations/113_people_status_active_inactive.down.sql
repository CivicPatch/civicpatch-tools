-- Exact reverse of 113. The constraint goes first: 'current'/'past' would violate it.
BEGIN;

ALTER TABLE people DROP CONSTRAINT IF EXISTS people_status_check;

UPDATE people SET status = 'current' WHERE status = 'active';
UPDATE people SET status = 'past' WHERE status = 'inactive';

ALTER TABLE people ALTER COLUMN status SET DEFAULT 'current';

COMMIT;
