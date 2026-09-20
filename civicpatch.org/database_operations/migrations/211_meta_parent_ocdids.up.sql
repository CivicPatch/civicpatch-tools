BEGIN;

-- Ancestry is ours, not a Popolo term, so it joins the `meta_` convention 199 adopted for
-- posts and 201 extended to memberships.
--
-- **Idempotency**: postgres has no `IF EXISTS` for `RENAME COLUMN`, so it is guarded on
-- the catalog, same idiom as 197.
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public' AND table_name = 'jurisdictions'
                 AND column_name = 'parent_ocdids') THEN
        ALTER TABLE jurisdictions RENAME COLUMN parent_ocdids TO meta_parent_ocdids;
    END IF;
END $$;

ALTER INDEX IF EXISTS jurisdictions_parent_ocdids_idx
    RENAME TO jurisdictions_meta_parent_ocdids_idx;

COMMIT;
