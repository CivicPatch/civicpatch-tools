BEGIN;

-- Rows from before 203 carry no organization. The changeset's own organization where it has one
-- (its memberships were written there at publish), else the jurisdiction's default, ordered as `get_default` does.
UPDATE source_records
SET organization_id = COALESCE(
    (SELECT changesets.organization_id FROM changesets WHERE changesets.id = source_records.changeset_id),
    (
        SELECT organizations.id FROM organizations
        WHERE organizations.jurisdiction_ocdid = source_records.jurisdiction_ocdid
        ORDER BY organizations.meta_is_default DESC, organizations.sort_order, organizations.name
        LIMIT 1
    )
)
WHERE organization_id IS NULL;

COMMIT;
