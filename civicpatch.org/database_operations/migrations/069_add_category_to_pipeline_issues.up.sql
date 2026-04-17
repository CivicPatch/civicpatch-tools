BEGIN;

ALTER TABLE pipeline_issues
    ADD COLUMN category text NOT NULL DEFAULT 'issue'
        CHECK (category IN ('error', 'issue'));

UPDATE pipeline_issues
SET category = 'error'
WHERE issue_type IN ('pipeline_error', 'no_info');

ALTER TABLE pipeline_issues ALTER COLUMN category DROP DEFAULT;

COMMIT;
