-- Restores the constraint only: which roles were candidates is not kept.

BEGIN;

ALTER TABLE roles DROP CONSTRAINT IF EXISTS roles_status_check;
ALTER TABLE roles ADD CONSTRAINT roles_status_check CHECK (
    status IN ('active', 'candidate', 'inactive')
);

COMMIT;
