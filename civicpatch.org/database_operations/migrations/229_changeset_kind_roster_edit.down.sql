-- Exactly reverses 229.

BEGIN;

ALTER TABLE changesets DROP CONSTRAINT IF EXISTS changesets_kind_check;
UPDATE changesets SET kind = 'people_edit' WHERE kind = 'roster_edit';
ALTER TABLE changesets ADD CONSTRAINT changesets_kind_check
    CHECK (kind = ANY (ARRAY['scrape', 'sheet_import', 'people_edit', 'jurisdiction_edit', 'rollback']));

DROP INDEX IF EXISTS changesets_one_open_review_edit_per_person;
CREATE UNIQUE INDEX changesets_one_open_review_edit_per_person
    ON changesets (parent_changeset_id, created_by_user_id)
    WHERE kind = 'people_edit' AND published_at IS NULL AND dismissed_at IS NULL;

COMMIT;
