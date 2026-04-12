BEGIN;

ALTER TABLE review_issues ADD COLUMN pull_request_url text;

COMMIT;
