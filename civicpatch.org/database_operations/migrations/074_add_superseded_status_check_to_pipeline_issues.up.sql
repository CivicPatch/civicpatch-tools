BEGIN;

ALTER TABLE pipeline_issues
    ADD CONSTRAINT pipeline_issues_status_check
        CHECK (status IN ('pending', 'pr_opened', 'resolved', 'superseded'));

COMMIT;
