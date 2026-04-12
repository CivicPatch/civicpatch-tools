BEGIN;

ALTER TABLE review_issues RENAME TO job_events;
ALTER TABLE job_events RENAME COLUMN issue_type TO event_type;

-- Drop new columns before restoring old structure
ALTER TABLE job_events
  DROP CONSTRAINT review_issues_issue_type_issue_key_unique,
  DROP COLUMN issue_key,
  DROP COLUMN status,
  DROP COLUMN resolved_at;

-- Restore single request_id FK column from first element of request_ids
ALTER TABLE job_events ADD COLUMN request_id UUID;
UPDATE job_events SET request_id = request_ids[1]::uuid;
ALTER TABLE job_events
  ALTER COLUMN request_id SET NOT NULL,
  DROP COLUMN request_ids;

ALTER TABLE job_events
  ADD CONSTRAINT job_events_request_id_fkey
  FOREIGN KEY (request_id) REFERENCES requests(id);

DROP INDEX IF EXISTS idx_review_issues_status;

ALTER INDEX IF EXISTS review_issues_issue_type_idx RENAME TO job_events_event_type_idx;

CREATE INDEX ON job_events (request_id);

COMMIT;
