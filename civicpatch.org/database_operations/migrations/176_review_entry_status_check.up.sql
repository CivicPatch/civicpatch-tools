-- `review_session_entries.status` had no CHECK, and its four values had no enum either:
-- `ReviewSessionEntryStatus` was a bare `class(str)`, so the members were unenumerable and
-- nothing could compare the column to them. The vocabulary lived as literals in 32 places
-- across five modules, plus this table's own default and the `active_claim` index predicate.
--
-- The comparable column with no constraint is `issues.issue_type`, which drifted far enough to
-- hold the string 'OPEN_ROUTER_TOKEN is not set'. This is the same shape, caught earlier.
--
-- Dev holds 12 rows, all 'resolved', so nothing needs folding first.

BEGIN;

ALTER TABLE review_session_entries DROP CONSTRAINT IF EXISTS review_session_entries_status_check;
ALTER TABLE review_session_entries ADD CONSTRAINT review_session_entries_status_check
    CHECK (status = ANY (ARRAY['claimed'::text, 'passed'::text, 'saved'::text, 'resolved'::text]));

COMMIT;
