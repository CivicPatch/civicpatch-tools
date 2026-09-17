BEGIN;

-- Back as it was: nullable, with the same foreign key. The values are not restored — which body a
-- changeset was "about" is not derivable once a review spans several.
ALTER TABLE changesets ADD COLUMN IF NOT EXISTS organization_id uuid;

ALTER TABLE changesets DROP CONSTRAINT IF EXISTS changesets_organization_id_fkey;
ALTER TABLE changesets
    ADD CONSTRAINT changesets_organization_id_fkey
    FOREIGN KEY (organization_id) REFERENCES organizations(id);

CREATE INDEX IF NOT EXISTS changesets_organization_id_idx ON changesets (organization_id);

COMMIT;
