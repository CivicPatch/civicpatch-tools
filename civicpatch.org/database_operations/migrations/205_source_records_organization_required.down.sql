BEGIN;

ALTER TABLE source_records DROP CONSTRAINT IF EXISTS source_records_organization_id_fkey;
ALTER TABLE source_records
    ADD CONSTRAINT source_records_organization_id_fkey
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE SET NULL;

ALTER TABLE source_records ALTER COLUMN organization_id DROP NOT NULL;

COMMIT;
