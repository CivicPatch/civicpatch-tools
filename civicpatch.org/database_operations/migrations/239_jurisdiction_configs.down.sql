BEGIN;

DELETE FROM activity WHERE type = 'sync_jurisdiction_config';
DELETE FROM activity_types WHERE type = 'sync_jurisdiction_config';

ALTER TABLE roles DROP COLUMN IF EXISTS config_path;
DROP TABLE IF EXISTS jurisdiction_configs;

COMMIT;
