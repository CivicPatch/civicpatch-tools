-- Every jurisdiction gets a default organization, not just the 3,438 that have ever published.
--
-- organizations.py used to mint one lazily, the first time a post or changeset needed it, on
-- the reasoning that syncing 9,524 rows ahead of demand wasn't worth it. That reasoning inverts
-- once source-page caching needs to key off `organization_id` rather than `jurisdiction_ocdid`
-- (jurisdictions are moving to multiple bodies) — a cache row has nowhere to attach for a
-- jurisdiction that has never published, so "every jurisdiction has one" becomes worth keeping
-- as an unconditional invariant instead of an incidental one. The open-data sync now creates
-- the default organization the moment a jurisdiction is upserted (regardless of active/inactive
-- status), so this migration only needs to cover what already existed before that changed.
BEGIN;

INSERT INTO organizations (jurisdiction_ocdid, name)
SELECT jurisdiction_ocdid, 'Government'
FROM jurisdictions
ON CONFLICT (jurisdiction_ocdid, name) DO NOTHING;

COMMIT;
