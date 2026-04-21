BEGIN;

ALTER TABLE pipeline_issues
    DROP CONSTRAINT pipeline_issues_status_check;

COMMIT;
