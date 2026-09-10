-- `change_logs` becomes `activity`, `change_log_types` becomes `activity_types`. Pure rename:
-- no column added, dropped or retyped.
--
-- This table has outgrown its name twice over already: it started as a log of edits, then
-- started carrying pipeline-run events too, and the home page's live feed (the reason for this
-- rename) reads it as neither logs nor changes but the thing a user watches happen. `activity`
-- is what both readers already call it in conversation.
--
-- Same idiom as 152 (`requests` -> `changesets`): constraint and index names come with it, or
-- the old vocabulary sits in the schema in a dozen places — the same drift `database/
-- pull_requests.py` querying a table it wasn't named for. See .scratch/2026-09-09-plan-
-- activity-wire.md, Phase 1 — the route `/api/v1/change_logs` is a contract and does NOT rename
-- here; only the table, its index-backed and plain constraints, and its explicit indexes do.
--
-- **Idempotency**: postgres has `IF EXISTS` for `ALTER TABLE` and `ALTER INDEX` but not for
-- `RENAME CONSTRAINT`, so those are guarded on the catalog, same as 152.
BEGIN;

ALTER TABLE IF EXISTS change_logs RENAME TO activity;
ALTER TABLE IF EXISTS change_log_types RENAME TO activity_types;

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'change_logs_type_fk') THEN
        ALTER TABLE activity RENAME CONSTRAINT change_logs_type_fk TO activity_type_fk;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'change_logs_user_id_fkey') THEN
        ALTER TABLE activity RENAME CONSTRAINT change_logs_user_id_fkey
            TO activity_user_id_fkey;
    END IF;
END $$;

ALTER INDEX IF EXISTS change_logs_pkey RENAME TO activity_pkey;
ALTER INDEX IF EXISTS idx_change_logs_changeset_id RENAME TO idx_activity_changeset_id;
ALTER INDEX IF EXISTS idx_change_logs_created_at RENAME TO idx_activity_created_at;
ALTER INDEX IF EXISTS idx_change_logs_jurisdiction_ocdid RENAME TO idx_activity_jurisdiction_ocdid;
ALTER INDEX IF EXISTS change_log_types_pkey RENAME TO activity_types_pkey;

COMMIT;
