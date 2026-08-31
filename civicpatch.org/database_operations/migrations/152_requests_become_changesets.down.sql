-- Exactly reverses 152. A rename loses nothing, so the round trip is clean: same rows, same
-- types, same constraints, same names as before.
--
-- Same guarding as the up migration, and in mirror order — indexes first, then constraints,
-- then columns, then the tables — so no statement refers to a name a later one is still using.
BEGIN;

ALTER INDEX IF EXISTS changesets_pkey RENAME TO requests_pkey;
ALTER INDEX IF EXISTS idx_changesets_batch_id RENAME TO idx_requests_batch_id;
ALTER INDEX IF EXISTS idx_changesets_jurisdiction_ocdid RENAME TO idx_requests_jurisdiction_ocdid;
ALTER INDEX IF EXISTS idx_changesets_status RENAME TO idx_requests_status;
ALTER INDEX IF EXISTS changeset_batches_pkey RENAME TO request_batches_pkey;
ALTER INDEX IF EXISTS changeset_batches_key_started_idx RENAME TO request_batches_key_started_idx;
ALTER INDEX IF EXISTS changeset_batches_one_running_per_key
    RENAME TO request_batches_one_running_per_key;
ALTER INDEX IF EXISTS source_records_changeset_id_idx RENAME TO source_records_request_id_idx;

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'changesets_publish_state_check') THEN
        ALTER TABLE changesets RENAME CONSTRAINT changesets_publish_state_check
            TO requests_publish_state_check;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_changesets_jurisdiction_ocdid') THEN
        ALTER TABLE changesets RENAME CONSTRAINT fk_changesets_jurisdiction_ocdid
            TO fk_requests_jurisdiction_ocdid;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'changesets_batch_id_fkey') THEN
        ALTER TABLE changesets RENAME CONSTRAINT changesets_batch_id_fkey
            TO requests_batch_id_fkey;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'changesets_requested_by_user_id_fkey') THEN
        ALTER TABLE changesets RENAME CONSTRAINT changesets_requested_by_user_id_fkey
            TO requests_requested_by_user_id_fkey;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'changesets_resolved_by_user_id_fkey') THEN
        ALTER TABLE changesets RENAME CONSTRAINT changesets_resolved_by_user_id_fkey
            TO requests_resolved_by_user_id_fkey;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'changeset_batches_kind_check') THEN
        ALTER TABLE changeset_batches RENAME CONSTRAINT changeset_batches_kind_check
            TO request_batches_kind_check;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'changeset_batches_status_check') THEN
        ALTER TABLE changeset_batches RENAME CONSTRAINT changeset_batches_status_check
            TO request_batches_status_check;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'changeset_batches_started_by_user_id_fkey') THEN
        ALTER TABLE changeset_batches RENAME CONSTRAINT changeset_batches_started_by_user_id_fkey
            TO request_batches_started_by_user_id_fkey;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'source_records_changeset_id_fkey') THEN
        ALTER TABLE source_records RENAME CONSTRAINT source_records_changeset_id_fkey
            TO source_records_request_id_fkey;
    END IF;
END $$;

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public' AND table_name = 'source_records'
                 AND column_name = 'changeset_id') THEN
        ALTER TABLE source_records RENAME COLUMN changeset_id TO request_id;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public' AND table_name = 'change_logs'
                 AND column_name = 'changeset_id') THEN
        ALTER TABLE change_logs RENAME COLUMN changeset_id TO request_id;
    END IF;
END $$;

ALTER TABLE IF EXISTS changesets RENAME TO requests;
ALTER TABLE IF EXISTS changeset_batches RENAME TO request_batches;

COMMIT;
