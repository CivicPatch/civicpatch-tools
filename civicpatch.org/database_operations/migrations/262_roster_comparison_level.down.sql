BEGIN;

ALTER TABLE roster_comparison_drafts DROP COLUMN IF EXISTS level;
ALTER TABLE roster_comparison_runs DROP COLUMN IF EXISTS level;

COMMIT;
