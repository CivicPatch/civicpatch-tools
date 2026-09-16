BEGIN;

-- The default body was found by its name, 'Government', which any maintainer can rename.
-- An explicit flag lets the default be renamed or reassigned, and leaves `sort_order` free to be
-- display order only. `meta_`: Popolo has no notion of a default organization.
ALTER TABLE organizations
    ADD COLUMN IF NOT EXISTS meta_is_default boolean NOT NULL DEFAULT false;

UPDATE organizations
SET meta_is_default = true
WHERE name = 'Government'
  AND NOT EXISTS (
      SELECT 1 FROM organizations flagged
      WHERE flagged.jurisdiction_ocdid = organizations.jurisdiction_ocdid
        AND flagged.meta_is_default
  );

CREATE UNIQUE INDEX IF NOT EXISTS organizations_one_default_per_jurisdiction
    ON organizations (jurisdiction_ocdid) WHERE meta_is_default;

COMMIT;
