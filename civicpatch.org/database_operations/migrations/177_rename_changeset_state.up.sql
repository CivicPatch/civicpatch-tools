-- `changesets.state` becomes `changeset_state`.
--
-- The generated column added by 164 had zero readers until 2026-09-05, and the reason was the
-- name: `jurisdictions.state` is the US state code with 34 readers, and nearly every query that
-- wants a changeset's lifecycle state also joins jurisdictions. Bare `state` in such a query is
-- ambiguous, so people re-derived the CASE by hand instead — `REVIEW_STATUS`, `WORK_IN_FLIGHT`,
-- `RESOLVED`, `PUBLISHED` are all the same expression written again.
--
-- `changeset_state`, not `lifecycle_state`: it is the same word as `ChangesetState`, and making
-- the Python name and the SQL name identical is the whole point. The stutter has precedent next
-- door in `issues.issue_type` and `issues.issue_key`. It also lets a shared fragment say
-- `changesets.changeset_state` unaliased, which CLAUDE.md requires of new ones.
--
-- The rename is what unblocks moving those hand-written fragments into `changeset_lifecycle`.

BEGIN;

ALTER TABLE changesets RENAME COLUMN state TO changeset_state;

COMMIT;
