-- Exact reverse of 157, same catalog guard.
BEGIN;

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public' AND table_name = 'changesets'
                 AND column_name = 'change_url') THEN
        ALTER TABLE changesets RENAME COLUMN change_url TO open_data_url;
    END IF;
END $$;

COMMIT;
