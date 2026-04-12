BEGIN;

ALTER TABLE review_issues DROP COLUMN pull_request_url;

COMMIT;
