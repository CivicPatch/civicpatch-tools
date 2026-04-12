BEGIN;

ALTER TABLE job_events RENAME TO review_issues;
ALTER TABLE review_issues RENAME COLUMN event_type TO issue_type;

ALTER TABLE review_issues
  ADD COLUMN issue_key   TEXT,
  ADD COLUMN request_ids TEXT[],
  ADD COLUMN status      TEXT NOT NULL DEFAULT 'pending',
  ADD COLUMN resolved_at TIMESTAMPTZ;

-- Backfill request_ids from the single request_id FK column
UPDATE review_issues SET request_ids = ARRAY[request_id::text];

-- Derive the issue_key per issue type
UPDATE review_issues
SET issue_key = CASE
  WHEN issue_type = 'unrecognized_role' THEN data->>'role'
  WHEN issue_type = 'dead_url'          THEN (data->>'url') || '::' || request_id::text
  ELSE request_id::text
END;

ALTER TABLE review_issues
  ALTER COLUMN request_ids SET NOT NULL,
  ALTER COLUMN issue_key SET NOT NULL;

-- Unique constraint enables upsert-by-key at write time
ALTER TABLE review_issues
  ADD CONSTRAINT review_issues_issue_type_issue_key_unique UNIQUE (issue_type, issue_key);

-- Drop old FK column; CASCADE also drops the auto-generated index on request_id
ALTER TABLE review_issues DROP COLUMN request_id;

-- Rename the auto-generated event_type index (created as CREATE INDEX ON job_events (event_type))
ALTER INDEX IF EXISTS job_events_event_type_idx RENAME TO review_issues_issue_type_idx;

CREATE INDEX idx_review_issues_status ON review_issues(status);

COMMIT;
