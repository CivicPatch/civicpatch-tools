BEGIN;

ALTER TABLE jobs ADD COLUMN github_run_id bigint;

COMMIT;
