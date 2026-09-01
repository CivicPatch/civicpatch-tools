-- Exact reverse of 156. Same catalog guards, same order inverted.
BEGIN;

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public' AND table_name = 'changesets'
                 AND column_name = 'created_by_user_id') THEN
        ALTER TABLE changesets RENAME COLUMN created_by_user_id TO requested_by_user_id;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public' AND table_name = 'review_session_entries'
                 AND column_name = 'changeset_ids') THEN
        ALTER TABLE review_session_entries RENAME COLUMN changeset_ids TO request_ids;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public' AND table_name = 'issues'
                 AND column_name = 'changeset_ids') THEN
        ALTER TABLE issues RENAME COLUMN changeset_ids TO request_ids;
    END IF;
END $$;

COMMIT;
