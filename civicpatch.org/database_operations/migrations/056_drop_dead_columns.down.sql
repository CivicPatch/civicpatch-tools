BEGIN;

ALTER TABLE jobs
    ADD COLUMN pull_request_review_state_to_delete TEXT,
    ADD COLUMN server_source TEXT,
    ADD COLUMN run_url TEXT;

ALTER TABLE pull_requests ADD COLUMN closed_at TIMESTAMPTZ;

ALTER TABLE jurisdictions
    ADD COLUMN file_path TEXT,
    ADD COLUMN git_commit TEXT;

ALTER TABLE people
    ADD COLUMN file_path TEXT,
    ADD COLUMN git_commit TEXT;

COMMIT;
