BEGIN;

-- The jsonb copy was left in place by the up migration, so rolling back only has to clear
-- what the backfill wrote. Rows a map run populated are indistinguishable from backfilled
-- ones here, and re-running GenerateMapsWorkflow restores those.
UPDATE jurisdictions
   SET meta_parent_ocdids = '{}'
 WHERE data ? 'parent_ocdids';

COMMIT;
