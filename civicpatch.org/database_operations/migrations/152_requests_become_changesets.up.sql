-- `requests` becomes `changesets`. Pure rename: no column added, dropped or retyped.
--
-- The table grew from "a job someone asked for", so its name fits only the oldest of its four
-- subtypes. Nobody *requests* a sheet import, and both hand-edit kinds are born published.
-- What all four are is a bundle of proposed changes to one jurisdiction, by one producer, at
-- one time, awaiting a decision — which is what OSM calls a changeset, down to the detail that
-- a changeset is legitimately open and empty while it is still being filled (a scrape row
-- exists at `status = PENDING, progress = 0` before it has any `source_records`).
--
-- `submissions` was rejected for exactly that reason: past tense, it misnames the whole
-- dispatched-and-running phase of a scrape. See `.scratch/2026-08-31-plan-changesets-model.md`.
--
-- Constraint and index names come too. A rename that leaves `requests_pkey` on `changesets`
-- puts the old vocabulary back into the schema in a dozen places, which is the same drift that
-- left `database/pull_requests.py` querying a table it is not named for.
--
-- `change_logs.request_id` renames as well, though the plan only listed `source_records`.
-- It is a text column holding these ids; leaving one behind is how half-renames start.
--
-- **Idempotency**: postgres has `IF EXISTS` for `ALTER TABLE` and `ALTER INDEX` but not for
-- `RENAME COLUMN` or `RENAME CONSTRAINT`, so those are guarded on the catalog. Explicit `IF`
-- per name rather than a loop over `format()` — dynamic SQL is harder to read than repetition.
BEGIN;

ALTER TABLE IF EXISTS requests RENAME TO changesets;
ALTER TABLE IF EXISTS request_batches RENAME TO changeset_batches;

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public' AND table_name = 'source_records'
                 AND column_name = 'request_id') THEN
        ALTER TABLE source_records RENAME COLUMN request_id TO changeset_id;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public' AND table_name = 'change_logs'
                 AND column_name = 'request_id') THEN
        ALTER TABLE change_logs RENAME COLUMN request_id TO changeset_id;
    END IF;
END $$;

-- Constraints. Index-backed ones (the primary keys, the unique lock index) are renamed by
-- ALTER INDEX below, which renames the constraint with them.
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'requests_publish_state_check') THEN
        ALTER TABLE changesets RENAME CONSTRAINT requests_publish_state_check
            TO changesets_publish_state_check;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_requests_jurisdiction_ocdid') THEN
        ALTER TABLE changesets RENAME CONSTRAINT fk_requests_jurisdiction_ocdid
            TO fk_changesets_jurisdiction_ocdid;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'requests_batch_id_fkey') THEN
        ALTER TABLE changesets RENAME CONSTRAINT requests_batch_id_fkey
            TO changesets_batch_id_fkey;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'requests_requested_by_user_id_fkey') THEN
        ALTER TABLE changesets RENAME CONSTRAINT requests_requested_by_user_id_fkey
            TO changesets_requested_by_user_id_fkey;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'requests_resolved_by_user_id_fkey') THEN
        ALTER TABLE changesets RENAME CONSTRAINT requests_resolved_by_user_id_fkey
            TO changesets_resolved_by_user_id_fkey;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'request_batches_kind_check') THEN
        ALTER TABLE changeset_batches RENAME CONSTRAINT request_batches_kind_check
            TO changeset_batches_kind_check;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'request_batches_status_check') THEN
        ALTER TABLE changeset_batches RENAME CONSTRAINT request_batches_status_check
            TO changeset_batches_status_check;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'request_batches_started_by_user_id_fkey') THEN
        ALTER TABLE changeset_batches RENAME CONSTRAINT request_batches_started_by_user_id_fkey
            TO changeset_batches_started_by_user_id_fkey;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'source_records_request_id_fkey') THEN
        ALTER TABLE source_records RENAME CONSTRAINT source_records_request_id_fkey
            TO source_records_changeset_id_fkey;
    END IF;
END $$;

ALTER INDEX IF EXISTS requests_pkey RENAME TO changesets_pkey;
ALTER INDEX IF EXISTS idx_requests_batch_id RENAME TO idx_changesets_batch_id;
ALTER INDEX IF EXISTS idx_requests_jurisdiction_ocdid RENAME TO idx_changesets_jurisdiction_ocdid;
ALTER INDEX IF EXISTS idx_requests_status RENAME TO idx_changesets_status;
ALTER INDEX IF EXISTS request_batches_pkey RENAME TO changeset_batches_pkey;
ALTER INDEX IF EXISTS request_batches_key_started_idx RENAME TO changeset_batches_key_started_idx;
ALTER INDEX IF EXISTS request_batches_one_running_per_key
    RENAME TO changeset_batches_one_running_per_key;
ALTER INDEX IF EXISTS source_records_request_id_idx RENAME TO source_records_changeset_id_idx;

COMMIT;
