BEGIN;

DROP INDEX IF EXISTS idx_jobs_has_issues;
ALTER TABLE jobs DROP COLUMN has_issues;
ALTER TABLE jobs ADD COLUMN review_json JSONB NOT NULL DEFAULT '[]';
ALTER TABLE jobs ADD COLUMN pull_request_review_state TEXT;

CREATE INDEX idx_jobs_pr_review_state ON jobs (pull_request_review_state);

COMMIT;
