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

-- Deduplicate rows that share the same (issue_type, issue_key) before adding the unique
-- constraint. The original job_events table stored one row per request, so the same role or
-- URL can appear across many requests. Here we:
--   1. Pick the oldest row in each group as the survivor.
--   2. Merge all request_ids into the survivor.
--   3. For unrecognized_role: rewrite data into the canonical {person_names:[...]} format,
--      aggregating person_name values from every row in the group.
--   4. Delete all non-survivor rows.
WITH survivors AS (
    SELECT DISTINCT ON (issue_type, issue_key) id, issue_type, issue_key
    FROM review_issues
    ORDER BY issue_type, issue_key, created_at ASC
),
merged_rids AS (
    SELECT issue_type, issue_key,
           array_agg(request_ids[1] ORDER BY request_ids[1]) AS all_rids
    FROM review_issues
    GROUP BY issue_type, issue_key
),
merged_names AS (
    SELECT issue_type, issue_key,
           jsonb_build_object(
               'person_names',
               jsonb_agg(DISTINCT (data->>'person_name') ORDER BY (data->>'person_name'))
           ) AS new_data
    FROM review_issues
    WHERE issue_type = 'unrecognized_role'
    GROUP BY issue_type, issue_key
)
UPDATE review_issues ri
SET
    request_ids = mr.all_rids,
    data        = COALESCE(mn.new_data, ri.data)
FROM survivors s
JOIN merged_rids mr ON mr.issue_type = s.issue_type AND mr.issue_key = s.issue_key
LEFT JOIN merged_names mn ON mn.issue_type = s.issue_type AND mn.issue_key = s.issue_key
WHERE ri.id = s.id;

DELETE FROM review_issues
WHERE id NOT IN (
    SELECT DISTINCT ON (issue_type, issue_key) id
    FROM review_issues
    ORDER BY issue_type, issue_key, created_at ASC
);

-- Unique constraint enables upsert-by-key at write time
ALTER TABLE review_issues
  ADD CONSTRAINT review_issues_issue_type_issue_key_unique UNIQUE (issue_type, issue_key);

-- Drop old FK column; CASCADE also drops the auto-generated index on request_id
ALTER TABLE review_issues DROP COLUMN request_id;

-- Rename the auto-generated event_type index (created as CREATE INDEX ON job_events (event_type))
ALTER INDEX IF EXISTS job_events_event_type_idx RENAME TO review_issues_issue_type_idx;

CREATE INDEX idx_review_issues_status ON review_issues(status);

COMMIT;
