BEGIN;

ALTER TABLE issues RENAME TO pipeline_issues;

COMMIT;
