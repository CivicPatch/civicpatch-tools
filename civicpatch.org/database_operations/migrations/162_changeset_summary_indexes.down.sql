BEGIN;

DROP INDEX IF EXISTS idx_changesets_created_at;
DROP INDEX IF EXISTS idx_changesets_pending_by_jurisdiction;
DROP INDEX IF EXISTS idx_jurisdictions_ocdid_state;

COMMIT;
