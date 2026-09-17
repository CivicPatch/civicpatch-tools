BEGIN;

-- Which body's extraction produced a sighting: the pipeline runs one extraction per organization
-- and stamps its id. Nullable — rows from before bodies, and records from sheet imports and
-- roster edits, have none. SET NULL so deleting an empty body is never blocked by old evidence.
ALTER TABLE source_records
    ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES organizations(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS source_records_organization_id_idx
    ON source_records (organization_id);

COMMIT;
