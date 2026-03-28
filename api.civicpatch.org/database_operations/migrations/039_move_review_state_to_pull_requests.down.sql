BEGIN;

ALTER TABLE jobs RENAME COLUMN pull_request_review_state_to_delete TO pull_request_review_state;

ALTER TABLE pull_requests DROP COLUMN IF EXISTS review_state;

COMMIT;
