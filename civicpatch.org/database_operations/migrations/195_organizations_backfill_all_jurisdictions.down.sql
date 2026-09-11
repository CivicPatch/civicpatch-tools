-- Exact reverse for the up/down round-trip: right after 195 runs, every default organization it
-- inserted is unreferenced (nothing has had time to attach a post or changeset to one), so this
-- removes exactly the rows 195 could have added. It cannot distinguish a backfilled row from one
-- organically created since, but by then something references it and this leaves it alone.
BEGIN;

DELETE FROM organizations o
WHERE o.name = 'Government'
  AND NOT EXISTS (SELECT 1 FROM posts p WHERE p.organization_id = o.id)
  AND NOT EXISTS (SELECT 1 FROM changesets c WHERE c.organization_id = o.id);

COMMIT;
