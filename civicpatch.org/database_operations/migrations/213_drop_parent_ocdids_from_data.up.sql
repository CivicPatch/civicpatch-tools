BEGIN;

-- Ancestry now has one home, `meta_parent_ocdids`, backfilled by 212 and written by the
-- boundary overlay. This clears the jsonb copy every reader has moved off. `updated_at` is
-- deliberately left alone: nothing about the jurisdiction changed, only where we keep it.
UPDATE jurisdictions
   SET data = data - 'parent_ocdids'
 WHERE data ? 'parent_ocdids';

COMMIT;
