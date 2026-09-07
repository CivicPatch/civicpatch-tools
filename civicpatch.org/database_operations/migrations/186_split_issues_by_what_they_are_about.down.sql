-- Restores the shape, not the deleted `merge_failed` rows — those are dropped by the up
-- migration because nothing can raise one, and a down migration cannot invent them back.
--
-- `issue_key` is rebuilt as the subject's id, which is what every surviving type used it for
-- once `unrecognized_role` was retired.

BEGIN;

CREATE TABLE IF NOT EXISTS issues (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    issue_type    text NOT NULL,
    data          jsonb NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    issue_key     text NOT NULL,
    changeset_ids text[] NOT NULL,
    status        text NOT NULL DEFAULT 'pending',
    resolved_at   timestamptz,
    is_flagged    boolean NOT NULL DEFAULT false
);

ALTER TABLE issues DROP CONSTRAINT IF EXISTS pipeline_issues_status_check;
ALTER TABLE issues ADD CONSTRAINT pipeline_issues_status_check
    CHECK (status IN ('pending', 'resolved', 'superseded'));

-- A run-side issue went back to naming its changeset where it had one, which is how the old
-- readers reached a jurisdiction; only a run that never minted one named the run itself.
INSERT INTO issues (issue_type, data, created_at, issue_key, changeset_ids, status, resolved_at, is_flagged)
SELECT i.issue_type, i.data, i.created_at,
       COALESCE(run.changeset_id::text, run.id::text),
       ARRAY[COALESCE(run.changeset_id::text, run.id::text)],
       i.status, i.resolved_at, i.is_flagged
FROM pipeline_run_issues i
JOIN pipeline_runs run ON run.id = i.pipeline_run_id;

INSERT INTO issues (issue_type, data, created_at, issue_key, changeset_ids, status, resolved_at, is_flagged)
SELECT i.issue_type, i.data, i.created_at,
       gen_random_uuid()::text, ARRAY[i.changeset_id::text],
       i.status, i.resolved_at, i.is_flagged
FROM changeset_issues i;

CREATE UNIQUE INDEX IF NOT EXISTS review_issues_issue_type_issue_key_unique
    ON issues (issue_type, issue_key);
CREATE INDEX IF NOT EXISTS idx_review_issues_status ON issues (status);
CREATE INDEX IF NOT EXISTS review_issues_issue_type_idx ON issues (issue_type);

DROP TABLE IF EXISTS pipeline_run_issues;
DROP TABLE IF EXISTS changeset_issues;

COMMIT;
