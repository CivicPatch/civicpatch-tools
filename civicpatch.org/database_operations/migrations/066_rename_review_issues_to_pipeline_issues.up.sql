BEGIN;

ALTER TABLE review_issues RENAME TO pipeline_issues;

COMMIT;
