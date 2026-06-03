BEGIN;

-- Reverse 099: reset global canonical priorities to the default and drop the
-- reorder_roles change_log type.

UPDATE role_terms
SET priority = 0
WHERE jurisdiction_ocdid IS NULL
  AND kind = 'canonical';

-- Remove reorder audit rows before the type they reference — change_logs.type
-- FKs change_log_types(type) with no cascade, so the type delete would abort
-- the rollback otherwise.
DELETE FROM change_logs WHERE type = 'reorder_roles';
DELETE FROM change_log_types WHERE type = 'reorder_roles';

COMMIT;
