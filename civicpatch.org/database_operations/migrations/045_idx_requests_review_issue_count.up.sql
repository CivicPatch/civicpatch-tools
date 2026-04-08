BEGIN;
CREATE INDEX idx_requests_review_issue_count ON requests ((jsonb_array_length(review_json->'issues')));
COMMIT;
