BEGIN;

ALTER TABLE pipeline_issues DROP COLUMN category;

COMMIT;
