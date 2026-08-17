-- Exact reverse of 114. The constraint goes first: 'current' would violate it.
BEGIN;

ALTER TABLE jurisdictions DROP CONSTRAINT IF EXISTS jurisdictions_status_check;

UPDATE jurisdictions SET status = 'current' WHERE status = 'active';

ALTER TABLE jurisdictions ALTER COLUMN status SET DEFAULT 'current';

COMMIT;
