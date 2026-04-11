BEGIN;

ALTER TABLE jobs
    DROP COLUMN pull_request_review_state_to_delete,
    DROP COLUMN server_source,
    DROP COLUMN run_url;

ALTER TABLE pull_requests DROP COLUMN closed_at;

ALTER TABLE jurisdictions
    DROP COLUMN file_path,
    DROP COLUMN git_commit;

ALTER TABLE people
    DROP COLUMN file_path,
    DROP COLUMN git_commit;

COMMIT;
