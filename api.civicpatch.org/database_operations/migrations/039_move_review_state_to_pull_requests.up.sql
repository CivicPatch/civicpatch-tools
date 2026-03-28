BEGIN;

ALTER TABLE pull_requests ADD COLUMN IF NOT EXISTS review_state TEXT;

UPDATE pull_requests pr
SET review_state = j.pull_request_review_state
FROM jobs j
WHERE j.request_id::uuid = pr.request_id;

ALTER TABLE jobs RENAME COLUMN pull_request_review_state TO pull_request_review_state_to_delete;

COMMIT;
