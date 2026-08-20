-- Reverses 121, in the order the constraints depend on each other: the unique index has to
-- exist again before the composite FK that needs it can be declared.
--
-- `status` comes back as 'candidate' for every row, which is what 118 minted and the only
-- value any post ever held — nothing promoted them. So this is a faithful restore, not a
-- lossy one.

BEGIN;

ALTER TABLE posts
    ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'candidate';

ALTER TABLE posts
    DROP CONSTRAINT IF EXISTS posts_status_check;

ALTER TABLE posts
    ADD CONSTRAINT posts_status_check
        CHECK (status IN ('candidate', 'active', 'inactive'));

ALTER TABLE organizations
    ADD CONSTRAINT organizations_jurisdiction_ocdid_id_key
        UNIQUE (jurisdiction_ocdid, id);

ALTER TABLE posts
    ADD CONSTRAINT posts_jurisdiction_ocdid_organization_id_fkey
        FOREIGN KEY (jurisdiction_ocdid, organization_id)
        REFERENCES organizations (jurisdiction_ocdid, id);

COMMIT;
