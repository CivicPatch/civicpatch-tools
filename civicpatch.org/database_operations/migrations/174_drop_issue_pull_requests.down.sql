BEGIN;

ALTER TABLE issues ADD COLUMN IF NOT EXISTS pull_request_url text;

ALTER TABLE issues DROP CONSTRAINT IF EXISTS pipeline_issues_status_check;
ALTER TABLE issues ADD CONSTRAINT pipeline_issues_status_check
    CHECK (status = ANY (ARRAY['pending'::text, 'pr_opened'::text, 'resolved'::text, 'superseded'::text]));

COMMIT;
