BEGIN;

ALTER INDEX IF EXISTS jurisdictions_meta_parent_ocdids_idx
    RENAME TO jurisdictions_parent_ocdids_idx;

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public' AND table_name = 'jurisdictions'
                 AND column_name = 'meta_parent_ocdids') THEN
        ALTER TABLE jurisdictions RENAME COLUMN meta_parent_ocdids TO parent_ocdids;
    END IF;
END $$;

COMMIT;
