BEGIN;

ALTER TABLE jobs DROP COLUMN issues;
ALTER TABLE jobs ADD COLUMN has_issues BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX idx_jobs_has_issues ON jobs (has_issues);

COMMIT;
