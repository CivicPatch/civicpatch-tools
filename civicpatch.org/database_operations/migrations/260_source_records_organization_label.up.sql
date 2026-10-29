-- The organization as the page writes it over the person (ExtractedPersonRecord.organization_label),
-- as `label` is the office: kept so a placement can be re-matched or repaired from the record.
-- Null for every row before this, and for sheet imports and edits, which have no page.

BEGIN;

ALTER TABLE source_records ADD COLUMN IF NOT EXISTS organization_label text;

COMMIT;
