BEGIN;

-- Rows referencing these must go first: change_logs.type is an FK to this table.
DELETE FROM change_logs WHERE type IN ('add_post', 'edit_post', 'delete_post');
DELETE FROM change_log_types WHERE type IN ('add_post', 'edit_post', 'delete_post');

COMMIT;
