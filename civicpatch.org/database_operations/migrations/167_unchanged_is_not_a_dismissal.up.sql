-- `unchanged` leaves `DismissalReason`, and the rows that carried it become publishes.
--
-- It described a scrape that re-confirmed the roster — "the scrape asserted nothing that needed
-- review" — and dismissed it. That is the wrong verb for the outcome: nothing was rejected and
-- nobody gave up. The roster was confirmed correct, which is a publish, and recording it as one
-- is what advances `memberships.last_seen_at` so the as-of timeline keeps moving.
--
-- The code no longer writes it. Every remaining dismissal names a literal reason at its call
-- site — `ERRORED` and `CANCELLED` from the run, `SUPERSEDED` from the sweeps, `REJECTED` from
-- a reviewer — and no request body can carry one, so nothing else can produce this value.
--
-- `changeset_summaries.CONFIRMED` was the only reader, as
-- `(published_at IS NOT NULL OR dismissed_reason = 'unchanged')`. Both halves meant the same
-- thing, which is why it collapses to the first once these rows move.
--
-- The 6 rows are re-confirmations of Seattle and Ellensburg. `published_at` takes the dismissal's
-- own timestamp: the decision happened then, only under the other name.
--
-- The column comment is refreshed too. 133 wrote it, and it has been stale twice over since:
-- it still says "the request left the pool" — the table was renamed to `changesets` — and it
-- names two values when there were five. Left alone it would now document one that cannot be
-- written at all.

BEGIN;

UPDATE changesets
   SET published_at     = dismissed_at,
       dismissed_at     = NULL,
       dismissed_reason = NULL
 WHERE dismissed_reason = 'unchanged';

ALTER TABLE changesets DROP CONSTRAINT IF EXISTS changesets_dismissed_reason_valid;
ALTER TABLE changesets ADD CONSTRAINT changesets_dismissed_reason_valid
    CHECK (dismissed_reason IS NULL
           OR dismissed_reason IN ('rejected', 'cancelled', 'errored', 'superseded'));

COMMENT ON COLUMN changesets.dismissed_reason IS
    'Why the changeset was dismissed. A person: rejected. A sweep: superseded. The run: errored, cancelled. NULL = published, in flight, or pre-dating this column.';

COMMIT;
