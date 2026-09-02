-- A changeset says which organization it is about.
--
-- A review is one organization at a time, and a person holds at most one open membership per
-- organization — so the organization is the scope every post in a changeset sits inside.
-- `posts_identity_uq` already says as much: `(organization_id, role_id, division_ocdid)`, the
-- organization being the scope and role + division the identity within it.
--
-- Until now the scope was implied. `posts.create_all` and `publications._bind_memberships` each
-- resolved it with one `organizations.find_or_create(cur, jurisdiction_ocdid)` outside their
-- loops, which is only right while a jurisdiction has exactly one organization — true today
-- (3,436 organizations across 3,436 jurisdictions, one distinct name) and only because
-- `find_or_create` always takes `DEFAULT_ORGANIZATION_NAME`.
--
-- Deliberately NOT on `DerivedPost`: a scrape reads a page and has no evidence for "this is the
-- school board rather than the council". Which body is being scraped is a targeting decision,
-- made when the changeset is created, exactly like `jurisdiction_ocdid`.
--
-- Nullable, and backfilled from each jurisdiction's single existing organization. Left nullable
-- rather than tightened in the same migration: nothing writes it yet, so a NOT NULL here would
-- fail every insert until the code catches up. Tightening is its own migration once it does.
BEGIN;

ALTER TABLE changesets ADD COLUMN IF NOT EXISTS organization_id uuid;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conname = 'changesets_organization_id_fkey') THEN
        ALTER TABLE changesets
            ADD CONSTRAINT changesets_organization_id_fkey
            FOREIGN KEY (organization_id) REFERENCES organizations(id);
    END IF;
END $$;

-- One organization per jurisdiction today, so this is unambiguous. A jurisdiction with none
-- (nothing has ever been published there) keeps NULL rather than minting an empty body.
UPDATE changesets c
SET organization_id = o.id
FROM organizations o
WHERE o.jurisdiction_ocdid = c.jurisdiction_ocdid
  AND c.organization_id IS NULL;

CREATE INDEX IF NOT EXISTS changesets_organization_idx
    ON changesets (organization_id);

COMMIT;
