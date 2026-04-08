BEGIN;

ALTER TABLE jobs ADD COLUMN jurisdiction_ocdid TEXT;
ALTER TABLE jobs ADD COLUMN has_issues BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE jobs SET jurisdiction_ocdid = arguments_json->>'jurisdiction_ocdid'
WHERE arguments_json IS NOT NULL;

CREATE INDEX idx_jobs_jurisdiction_ocdid_col ON jobs (jurisdiction_ocdid);
CREATE INDEX idx_jobs_has_issues ON jobs (has_issues);

COMMIT;