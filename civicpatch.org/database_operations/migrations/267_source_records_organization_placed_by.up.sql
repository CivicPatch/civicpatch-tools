-- What placed a scraped record in its organization (pipeline 3's placement steps, mirrors
-- OrganizationPlacedBy); null when ingest's default did, and for sheets, edits and older rows.

BEGIN;

ALTER TABLE source_records ADD COLUMN IF NOT EXISTS organization_placed_by text;
ALTER TABLE source_records DROP CONSTRAINT IF EXISTS source_records_organization_placed_by_check;
ALTER TABLE source_records ADD CONSTRAINT source_records_organization_placed_by_check CHECK (
    organization_placed_by IS NULL OR organization_placed_by IN ('role', 'heading', 'jev', 'llm')
);

COMMIT;
