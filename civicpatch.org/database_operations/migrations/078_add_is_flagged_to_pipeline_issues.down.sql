BEGIN;
ALTER TABLE pipeline_issues DROP COLUMN is_flagged;
COMMIT;
