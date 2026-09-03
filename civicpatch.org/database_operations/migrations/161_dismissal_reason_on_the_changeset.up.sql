-- One home for "why was this dismissed".
--
-- The reason was being written to two places by two code paths and read from one: the sweeps
-- (`dismiss_as_unchanged`, `dismiss_superseded_by`) set `changesets.dismissed_reason`, while
-- `dismiss_request` sent it only to the `close_review` change_log. Measured before this ran,
-- across every dismissed changeset on dev: 256 had the column and no log, 10 had the log and
-- no column, and **zero had both**. Not two stores that drifted — one column's job split down
-- the middle by which path did the dismissing.
--
-- So readers had to COALESCE the two, which meant a `change_logs` join and a `DISTINCT ON` in
-- every query that wanted an outcome. `get_jurisdiction_history` did not, and rendered 249 of
-- 381 resolved changesets as "Dismissed / unknown" when the column knew they were superseded
-- or unchanged.
--
-- `dismiss_request` now writes the column too. This carries the rows written before it did,
-- settles the one value that was never in the enum, and adds the CHECK that keeps it that way.
--
-- The four live producers all write a valid reason now: `dismiss_as_unchanged`,
-- `dismiss_superseded_by` and `supersede_stacked_requests` always did, and `dismiss_request`
-- does as of this change.

BEGIN;

-- Idempotent by its WHERE clause: a second run finds nothing NULL left to fill. Takes the
-- newest log per changeset, matching how readers resolved it.
UPDATE changesets r
   SET dismissed_reason = latest.reason
  FROM (
      SELECT DISTINCT ON (cl.changeset_id)
             cl.changeset_id,
             cl.changes->>'reason' AS reason
      FROM change_logs cl
      WHERE cl.type = 'close_review'
        AND cl.changes->>'reason' IS NOT NULL
      ORDER BY cl.changeset_id, cl.created_at DESC
  ) AS latest
 WHERE r.id::text = latest.changeset_id
   AND r.dismissed_at IS NOT NULL
   AND r.dismissed_reason IS NULL;

-- The one value that was never in `DismissalReason`. 7 rows, all SUCCESS scrapes, all dismissed
-- on 2026-08-25 by `one_offs/03_discard_unreviewed_scrapes.py`, which declared `discarded` as
-- its own local constant. That script is spent — it still says `UPDATE requests`, a table 152
-- renamed — so nothing writes this value any more.
--
-- To NULL rather than to a neighbouring reason: it meant "nobody read it and nobody will",
-- which no enum member says. NULL reads as "unknown", which is the truth — we can no longer
-- express why these were dismissed. Mapping them onto `cancelled` or `superseded` would assert
-- something about the roster that never happened.
UPDATE changesets
   SET dismissed_reason = NULL
 WHERE dismissed_reason = 'discarded';

-- What the run's own status already records. Not a guess: a changeset whose pipeline ended in
-- ERROR errored, and one that was CANCELLED was cancelled — `status` is the run's recorded
-- outcome, not an inference from it. 20 rows on dev, dismissed before any reason was stored.
--
-- Deliberately stops there. 19 more are dismissed SUCCESS runs with nothing anywhere saying
-- why, scattered across eight dates rather than one operation. Giving them a reason would
-- invent history; they stay NULL and read as "Dismissed".
UPDATE changesets
   SET dismissed_reason = CASE status
       WHEN 'ERROR'     THEN 'errored'
       WHEN 'CANCELLED' THEN 'cancelled'
   END
 WHERE dismissed_at IS NOT NULL
   AND dismissed_reason IS NULL
   AND status IN ('ERROR', 'CANCELLED');

-- Keeps it settled. Without this the column is plain `text` and the frontend's labels and pill
-- colours are a promise nothing enforces — which is exactly how `discarded` got in.
--
-- NULL stays legal, and is not a hole to be plugged later: it means "dismissed before we
-- recorded why". All four live producers write a reason now — `dismiss_as_unchanged`,
-- `dismiss_superseded_by`, `supersede_stacked_requests` and `dismiss_request` — so the NULL
-- branch is closed to new rows and only ever shrinks. A NOT NULL here would force 19 rows to
-- be given reasons nobody recorded.
ALTER TABLE changesets DROP CONSTRAINT IF EXISTS changesets_dismissed_reason_valid;
ALTER TABLE changesets ADD CONSTRAINT changesets_dismissed_reason_valid
    CHECK (dismissed_reason IS NULL OR dismissed_reason = ANY (ARRAY[
        'rejected', 'cancelled', 'errored', 'superseded', 'unchanged'
    ]));

COMMIT;
