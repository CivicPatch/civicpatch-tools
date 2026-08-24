BEGIN;

DELETE FROM change_logs WHERE type = 'assert_field';
DELETE FROM change_log_types WHERE type = 'assert_field';

COMMIT;
