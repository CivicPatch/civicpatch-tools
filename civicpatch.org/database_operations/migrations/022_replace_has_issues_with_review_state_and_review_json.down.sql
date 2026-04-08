BEGIN;

DROP INDEX IF EXISTS idx_jobs_pr_review_state;
ALTER TABLE jobs DROP COLUMN pull_request_review_state;
ALTER TABLE jobs DROP COLUMN review_json;
ALTER TABLE jobs ADD COLUMN has_issues BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX idx_jobs_has_issues ON jobs (has_issues);

COMMIT;
