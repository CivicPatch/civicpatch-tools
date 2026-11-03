-- Rows the user agreed to leave out of a comparison, so the report can say so.

BEGIN;

ALTER TABLE roster_comparison_runs
    ADD COLUMN IF NOT EXISTS left_out_rows jsonb NOT NULL DEFAULT '[]'::jsonb;

COMMIT;
