-- Retire `pr_opened` and `issues.pull_request_url`.
--
-- The status was unreachable. `open_issue_pull_request` was its only writer and had zero
-- callers, so nothing ever set it or `pull_request_url`; the GitHub webhook that looked an
-- issue up by that url could therefore never match one. Dev held 0 rows in either state.
--
-- It is a vestige of the era when resolving an issue meant opening a `resolve/` PR against
-- open-data. Rosters commit straight to main now, and the one surviving PR path — the
-- jurisdiction edit — never touched this column: it polls mergeability and merges directly.
--
-- Rows are folded to `pending` before the CHECK tightens, so a prod row from that era becomes
-- an open issue a human can act on rather than a constraint violation.

BEGIN;

UPDATE issues SET status = 'pending' WHERE status = 'pr_opened';

ALTER TABLE issues DROP CONSTRAINT IF EXISTS pipeline_issues_status_check;
ALTER TABLE issues ADD CONSTRAINT pipeline_issues_status_check
    CHECK (status = ANY (ARRAY['pending'::text, 'resolved'::text, 'superseded'::text]));

ALTER TABLE issues DROP COLUMN IF EXISTS pull_request_url;

COMMIT;
