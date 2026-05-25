BEGIN;

-- The review unit is the PR (request_id), not the jurisdiction: a jurisdiction can
-- have multiple PRs over time, and tracking by ocdid wrongly excludes the later ones
-- from the same session. Track reviewed request_ids instead.
ALTER TABLE review_sessions RENAME COLUMN reviewed_ocdids TO reviewed_request_ids;

COMMIT;
