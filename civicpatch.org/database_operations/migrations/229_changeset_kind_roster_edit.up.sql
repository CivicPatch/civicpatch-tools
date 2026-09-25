-- The kind people_edit becomes roster_edit: it carries post assignments, labels, term dates and
-- merges as well as person fields, and pairs with jurisdiction_edit (that one edits the
-- jurisdiction, this one its roster). The CHECK and 223's partial index name the value.

BEGIN;

ALTER TABLE changesets DROP CONSTRAINT IF EXISTS changesets_kind_check;
UPDATE changesets SET kind = 'roster_edit' WHERE kind = 'people_edit';
ALTER TABLE changesets ADD CONSTRAINT changesets_kind_check
    CHECK (kind = ANY (ARRAY['scrape', 'sheet_import', 'roster_edit', 'jurisdiction_edit', 'rollback']));

DROP INDEX IF EXISTS changesets_one_open_review_edit_per_person;
CREATE UNIQUE INDEX changesets_one_open_review_edit_per_person
    ON changesets (parent_changeset_id, created_by_user_id)
    WHERE kind = 'roster_edit' AND published_at IS NULL AND dismissed_at IS NULL;

COMMIT;
