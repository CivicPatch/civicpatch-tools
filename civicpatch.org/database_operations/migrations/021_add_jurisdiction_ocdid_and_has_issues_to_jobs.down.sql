BEGIN;

DROP INDEX IF EXISTS idx_jobs_jurisdiction_ocdid_col;
DROP INDEX IF EXISTS idx_jobs_has_issues;

ALTER TABLE jobs DROP COLUMN jurisdiction_ocdid;
ALTER TABLE jobs DROP COLUMN has_issues;

COMMIT;