-- Exactly reverses 190. A rename loses nothing, so the round trip is clean: same rows, same
-- types, same constraints, same names as before.
--
-- Same guarding as the up migration, and in mirror order — indexes first, then constraints,
-- then the tables — so no statement refers to a name a later one is still using.
BEGIN;

ALTER INDEX IF EXISTS activity_pkey RENAME TO change_logs_pkey;
ALTER INDEX IF EXISTS idx_activity_changeset_id RENAME TO idx_change_logs_changeset_id;
ALTER INDEX IF EXISTS idx_activity_created_at RENAME TO idx_change_logs_created_at;
ALTER INDEX IF EXISTS idx_activity_jurisdiction_ocdid RENAME TO idx_change_logs_jurisdiction_ocdid;
ALTER INDEX IF EXISTS activity_types_pkey RENAME TO change_log_types_pkey;

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'activity_type_fk') THEN
        ALTER TABLE activity RENAME CONSTRAINT activity_type_fk TO change_logs_type_fk;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'activity_user_id_fkey') THEN
        ALTER TABLE activity RENAME CONSTRAINT activity_user_id_fkey
            TO change_logs_user_id_fkey;
    END IF;
END $$;

ALTER TABLE IF EXISTS activity RENAME TO change_logs;
ALTER TABLE IF EXISTS activity_types RENAME TO change_log_types;

COMMIT;
