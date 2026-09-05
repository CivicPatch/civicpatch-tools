-- One word for one state, and one enum fewer.
--
-- The generated column said 'ready'; `RequestReviewStatus` said 'pending'; `ChangesetState`
-- said READY. Three names, and nothing forced them to agree — the column had zero readers, so
-- nothing ever noticed.
--
-- 'open' wins on merit, not on what was already exposed:
--
--   * 'pending' is taken. `issues.status` means something else by it, and the two appear in one
--     sentence constantly — an *open* changeset carrying *pending* issues.
--   * 'open' is the vocabulary this table is already named after. DATABASE.md's own note on why
--     it is called `changesets`: "exactly the state an OSM changeset models as open-and-empty".
--   * It is the complement of a predicate that already exists. `RESOLVED` is `published_at IS
--     NOT NULL OR dismissed_at IS NOT NULL`, alongside `resolved_by_user_id` and `resolved_at`.
--     Open is simply not-resolved.
--   * 'ready' fails on its own terms: ready implies ready *for* something, and the two
--     hand-edit kinds are born published and never are.
--
-- `RequestReviewStatus` is deleted rather than kept in step with `ChangesetState` forever, and
-- `review_status` goes with it: three of the four kinds are born published and never reviewed,
-- so the field named the wrong thing. It is `changeset_state` end to end now, frontend included.
--
-- A generated column's expression cannot be altered in place, so it is dropped and re-added.
-- No data moves: every value is computed from the two timestamps beside it.

BEGIN;

ALTER TABLE changesets DROP COLUMN IF EXISTS changeset_state;
ALTER TABLE changesets ADD COLUMN IF NOT EXISTS changeset_state text
    GENERATED ALWAYS AS (
        CASE
            WHEN published_at IS NOT NULL THEN 'published'
            WHEN dismissed_at IS NOT NULL THEN 'dismissed'
            ELSE 'open'
        END
    ) STORED;

COMMIT;
