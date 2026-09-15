-- Exactly reverses 198.
BEGIN;

ALTER TABLE organizations
    DROP COLUMN IF EXISTS url;

COMMIT;
