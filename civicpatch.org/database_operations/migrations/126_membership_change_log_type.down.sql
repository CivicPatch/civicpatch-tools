BEGIN;

-- Rows referencing it must go first: change_logs.type is an FK to this table.
DELETE FROM change_logs WHERE type = 'assign_membership';
DELETE FROM change_log_types WHERE type = 'assign_membership';

COMMIT;
