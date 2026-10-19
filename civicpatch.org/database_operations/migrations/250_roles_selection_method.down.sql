BEGIN;

ALTER TABLE roles DROP CONSTRAINT IF EXISTS roles_selection_method_check;
ALTER TABLE roles DROP COLUMN IF EXISTS selection_method;

COMMIT;
