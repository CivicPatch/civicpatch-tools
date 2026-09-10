BEGIN;

ALTER TABLE changesets DROP CONSTRAINT IF EXISTS changesets_kind_check;
ALTER TABLE changesets ADD CONSTRAINT changesets_kind_check
    CHECK (kind IN ('scrape', 'sheet_import', 'people_edit', 'jurisdiction_edit'));

DROP INDEX IF EXISTS changesets_parent_changeset_id_idx;

ALTER TABLE changesets
    DROP COLUMN IF EXISTS parent_changeset_id;

COMMIT;
