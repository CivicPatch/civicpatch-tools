BEGIN;

-- Every source record belongs to an organization: ingest stamps it (default when unstamped), and
-- 204 backfilled the rest. RESTRICT: `organizations.delete` moves a body's records to the default
-- first, so a delete that would orphan evidence is a bug, not a cleanup.
ALTER TABLE source_records ALTER COLUMN organization_id SET NOT NULL;

ALTER TABLE source_records DROP CONSTRAINT IF EXISTS source_records_organization_id_fkey;
ALTER TABLE source_records
    ADD CONSTRAINT source_records_organization_id_fkey
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE RESTRICT;

COMMIT;
