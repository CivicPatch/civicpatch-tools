-- Exact reverse of 158. The index and constraint go with the column, but dropped explicitly so
-- the rollback reads as the inverse rather than relying on cascade.
BEGIN;

DROP INDEX IF EXISTS changesets_organization_idx;

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint
               WHERE conname = 'changesets_organization_id_fkey') THEN
        ALTER TABLE changesets DROP CONSTRAINT changesets_organization_id_fkey;
    END IF;
END $$;

ALTER TABLE changesets DROP COLUMN IF EXISTS organization_id;

COMMIT;
