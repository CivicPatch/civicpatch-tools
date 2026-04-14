BEGIN;

ALTER TABLE pipeline_issues RENAME TO review_issues;

COMMIT;
