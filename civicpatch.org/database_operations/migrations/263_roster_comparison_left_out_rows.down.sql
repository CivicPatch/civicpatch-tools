BEGIN;

ALTER TABLE roster_comparison_runs DROP COLUMN IF EXISTS left_out_rows;

COMMIT;
