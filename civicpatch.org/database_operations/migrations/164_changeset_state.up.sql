-- `changesets.state`: the lifecycle, computed once instead of spelled out ten times.
--
-- Where a changeset *is* was derived independently in ten places, each a different combination
-- of `status`, `published_at`, `dismissed_at` and `kind`:
--
--   REVIEW_STATUS, WORK_IN_FLIGHT, AVAILABLE_FOR_REVIEW, RUN_IN_FLIGHT, SWEEPABLE,
--   HELD_BY_REVIEWER   (database/changesets.py)
--   RESOLVED           (database/jurisdictions.py)
--   CONFIRMED, FAILED, COLLECTED  (database/changeset_summaries.py)
--
-- GENERATED, not written: it cannot drift from the columns it is computed from, no write path
-- has to remember it, and renaming a state is a migration rather than a data migration. The
-- Python side is `core/changeset_lifecycle.py`, whose `ChangesetState` these values match.
--
-- Ordering is the definition. Published wins over everything: a changeset that published is
-- published whatever its run did afterwards. Then dismissed, then the run's own outcome.
--
-- `status` carries both lifecycle values and step names — SCRAPE_PAGE, CLEANUP, SEND_SUCCESS —
-- so anything that is not terminal is progress, which is why the ELSE is 'running'.
--
-- Three of the ten predicates cannot be folded in here and stay as they are:
-- `AVAILABLE_FOR_REVIEW` and `HELD_BY_REVIEWER` reach `source_records`, `issues` and
-- `review_session_entries`, and a generated column may only read its own row.

BEGIN;

ALTER TABLE changesets ADD COLUMN IF NOT EXISTS state text
    GENERATED ALWAYS AS (
        CASE
            WHEN published_at IS NOT NULL THEN 'published'
            WHEN dismissed_at IS NOT NULL THEN 'dismissed'
            WHEN status IN ('ERROR', 'CANCELLED') THEN 'failed'
            WHEN status IS NULL OR status IN ('SUCCESS', 'RESOLVED') THEN 'ready'
            ELSE 'running'
        END
    ) STORED;

CREATE INDEX IF NOT EXISTS changesets_state_idx ON changesets (state);

COMMIT;
