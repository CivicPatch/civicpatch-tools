BEGIN;

ALTER TABLE change_logs DROP CONSTRAINT IF EXISTS change_logs_type_fk;
DROP TABLE IF EXISTS change_log_types;

ALTER TABLE change_logs ADD CONSTRAINT change_logs_type_valid CHECK (type IN (
    'merge_review', 'close_review',
    'add_person', 'edit_person', 'delete_person', 'edit_jurisdiction'
));

DROP TABLE IF EXISTS role_aliases;
DROP TABLE IF EXISTS role_terms;

COMMIT;
