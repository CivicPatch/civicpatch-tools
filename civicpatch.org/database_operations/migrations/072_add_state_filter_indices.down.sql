BEGIN;

DROP INDEX IF EXISTS idx_requests_jurisdiction_ocdid;
DROP INDEX IF EXISTS idx_pull_requests_status;

COMMIT;
