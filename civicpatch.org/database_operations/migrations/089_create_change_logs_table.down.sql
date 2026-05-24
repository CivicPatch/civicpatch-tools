BEGIN;
DROP INDEX IF EXISTS idx_change_logs_jurisdiction_ocdid;
DROP INDEX IF EXISTS idx_change_logs_created_at;
DROP TABLE IF EXISTS change_logs;
COMMIT;
