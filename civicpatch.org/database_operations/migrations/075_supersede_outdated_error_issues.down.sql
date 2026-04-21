BEGIN;

-- Revert superseded error issues back to pending.
-- Note: this cannot perfectly reconstruct the original state — issues that were
-- already resolved or pr_opened before the backfill are unaffected (they remain
-- in their current status), so this only restores the backfill-superseded rows.
UPDATE pipeline_issues
SET status = 'pending', resolved_at = NULL
WHERE category = 'error'
  AND status = 'superseded';

COMMIT;
