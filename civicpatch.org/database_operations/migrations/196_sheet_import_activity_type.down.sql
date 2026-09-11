BEGIN;

DELETE FROM activity WHERE type = 'sheet_import';
DELETE FROM activity_types WHERE type = 'sheet_import';

COMMIT;
