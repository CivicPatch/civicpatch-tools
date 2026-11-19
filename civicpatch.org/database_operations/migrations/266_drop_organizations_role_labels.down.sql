-- The column comes back empty: what it held is not recoverable, and nothing reads it.

BEGIN;

ALTER TABLE organizations ADD COLUMN IF NOT EXISTS extras_role_labels jsonb NOT NULL DEFAULT '{}'::jsonb;

COMMIT;
