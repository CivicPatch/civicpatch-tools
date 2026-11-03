-- One comparison compares one level of a state's jurisdictions; every run so far was local.

BEGIN;

ALTER TABLE roster_comparison_runs
    ADD COLUMN IF NOT EXISTS level text NOT NULL DEFAULT 'local';

ALTER TABLE roster_comparison_drafts
    ADD COLUMN IF NOT EXISTS level text NOT NULL DEFAULT 'local';

ALTER TABLE roster_comparison_runs
    DROP CONSTRAINT IF EXISTS roster_comparison_runs_level_check;
ALTER TABLE roster_comparison_runs
    ADD CONSTRAINT roster_comparison_runs_level_check CHECK (level IN ('state', 'counties', 'local'));

ALTER TABLE roster_comparison_drafts
    DROP CONSTRAINT IF EXISTS roster_comparison_drafts_level_check;
ALTER TABLE roster_comparison_drafts
    ADD CONSTRAINT roster_comparison_drafts_level_check CHECK (level IN ('state', 'counties', 'local'));

COMMIT;
