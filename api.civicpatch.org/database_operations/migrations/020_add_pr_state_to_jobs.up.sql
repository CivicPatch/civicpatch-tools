BEGIN;

ALTER TABLE jobs
    ADD COLUMN pull_request_status    TEXT,
    ADD COLUMN pull_request_merged_at TIMESTAMPTZ;

CREATE INDEX idx_jobs_pull_request_status ON jobs(pull_request_status);
CREATE INDEX idx_jobs_jurisdiction_ocdid  ON jobs ((arguments_json->>'jurisdiction_ocdid'));

COMMIT;
