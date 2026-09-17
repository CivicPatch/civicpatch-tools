BEGIN;

-- A review is no longer about one body: a scrape reads every body it has a page for, the
-- derivation puts each person in the body that sighted them, and publishing closes only in the
-- bodies this changeset read (`source_records.organization_id`). Nothing reads this column now.
ALTER TABLE changesets DROP COLUMN IF EXISTS organization_id;

COMMIT;
