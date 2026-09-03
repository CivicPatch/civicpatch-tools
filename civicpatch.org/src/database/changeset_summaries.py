"""Changeset activity rolled up per state, for the cross-state summary page.

The per-jurisdiction view of the same subject is `get_jurisdiction_history`; this is the same
question one zoom level out. Where the two overlap they must agree, so the outcome is read the
same way in both: off `changesets.dismissed_reason`, the changeset's own state.
"""

import logging

from database.changesets import AVAILABLE_FOR_REVIEW, RUN_IN_FLIGHT
from database.database import get_pool
from database.jurisdictions import ROSTER_CHANGE_TYPES
from psycopg.rows import dict_row
from schemas.changeset_summaries import (
    BucketPage,
    BucketRow,
    CalendarDay,
    StateRollup,
)
from shared.utils.statuses import (
    SOURCE_READING_KINDS,
    ChangesetKind,
    DismissalReason,
    PipelineRunStatus,
)

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_DAYS = 30

COLLECTION_KINDS = [k.value for k in SOURCE_READING_KINDS]

# The buckets a state's section breaks into.
BUCKET_REVIEW = "review"
BUCKET_FAILED = "failed"
BUCKET_OK = "ok"

# Defined once so the rollup, calendar and bucket cannot disagree. All need `changesets` as `r`.
# `unchanged` is confirmed — a re-confirmed roster is a healthy outcome.
CONFIRMED = (
    "(r.published_at IS NOT NULL "
    f"OR r.dismissed_reason = '{DismissalReason.UNCHANGED.value}')"
)

# `status` too: a run that errored before recording a reason still errored.
# Only collection attempts get an outcome. A hand edit has no run to fail — 8 dev `people_edit`
# rows, none with a status — so it would land in `ok` and pad the green band with something that
# never ran. `jurisdiction_edit` is outside `AVAILABLE_FOR_REVIEW` besides, so it could never be
# "to review" and would skew one band permanently.
COLLECTED = "r.kind = ANY(%(collection_kinds)s)"

FAILED = (
    f"(r.dismissed_reason IN ('{DismissalReason.REJECTED.value}', "
    f"'{DismissalReason.ERRORED.value}', '{DismissalReason.CANCELLED.value}') "
    f"OR r.status = '{PipelineRunStatus.ERROR.value}')"
)

# Each side aggregates to one row per state before joining — measured, ~114 ms at 571k
# changesets. Joining first spilled to disk. Served live; no cache.
STATE_ROLLUP_SQL = f"""
-- THE STOCK. Unwindowed: an item waiting 90 days is still waiting.
-- `AVAILABLE_FOR_REVIEW` verbatim, never a copy — a copy drifts from the pool it mirrors.
-- `DISTINCT ON` because the supersede sweep leaves transient duplicates.
WITH valid_queue AS (
    SELECT DISTINCT ON (r.jurisdiction_ocdid)
           r.jurisdiction_ocdid, r.sourced_at
    FROM changesets r
    WHERE {AVAILABLE_FOR_REVIEW}
    ORDER BY r.jurisdiction_ocdid, r.sourced_at DESC
),
-- Unwindowed on purpose: a run started before the window is still running, and this gates the
-- scrape button. Missing one would offer a second batch on top of a live one.
running AS (
    SELECT j.state, count(*)::int AS running
    FROM changesets r
    JOIN jurisdictions j USING (jurisdiction_ocdid)
    WHERE {RUN_IN_FLIGHT}
    GROUP BY j.state
),
queue AS (
    SELECT j.state,
           count(*)::int                                    AS to_review,
           max(date_part('day', now() - q.sourced_at))::int AS oldest_days
    FROM valid_queue q
    JOIN jurisdictions j USING (jurisdiction_ocdid)
    GROUP BY j.state
),
-- THE FLOWS. Windowed events; pending belongs to the queue above.
-- A dismissal with no reason falls through every FILTER, which is the honest answer.
flows AS (
    SELECT j.state,
           count(*) FILTER (WHERE {CONFIRMED})::int AS confirmed,
           count(*) FILTER (
               WHERE r.dismissed_reason = '{DismissalReason.REJECTED.value}'
           )::int AS rejected,
           count(*) FILTER (
               WHERE r.dismissed_reason = '{DismissalReason.ERRORED.value}'
                  OR r.status = '{PipelineRunStatus.ERROR.value}'
           )::int AS errored,
           max(r.created_at) AS last_run_at
    FROM changesets r
    JOIN jurisdictions j USING (jurisdiction_ocdid)
    WHERE r.created_at >= now() - %(window)s::interval
      AND {COLLECTED}
    GROUP BY j.state
),
-- An allow-list, same one the timeline uses: counting review lifecycle would report
-- bookkeeping as roster movement. An unlisted type undercounts, which is the safe direction.
edits AS (
    SELECT j.state, count(*)::int AS roster_edits
    FROM change_logs cl
    JOIN jurisdictions j USING (jurisdiction_ocdid)
    WHERE cl.created_at >= now() - %(window)s::interval
      AND cl.type = ANY(%(roster_types)s)
    GROUP BY j.state
)
SELECT
    j.state,
    COALESCE(q.to_review, 0)    AS to_review,
    COALESCE(q.oldest_days, 0)  AS oldest_days,
    COALESCE(f.confirmed, 0)    AS confirmed,
    COALESCE(f.rejected, 0)     AS rejected,
    COALESCE(f.errored, 0)      AS errored,
    COALESCE(e.roster_edits, 0) AS roster_edits,
    COALESCE(rn.running, 0)     AS running,
    f.last_run_at
FROM (SELECT DISTINCT state FROM jurisdictions) j
LEFT JOIN running rn USING (state)
LEFT JOIN queue q USING (state)
LEFT JOIN flows f USING (state)
LEFT JOIN edits e USING (state)
ORDER BY to_review DESC, j.state;
"""


async def get_state_rollup(
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> list[StateRollup]:
    """Every state appears, silent ones included — nothing running is a fact worth showing."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            STATE_ROLLUP_SQL,
            {
                "window": f"{window_days} days",
                "roster_types": [t.value for t in ROSTER_CHANGE_TYPES],
                "collection_kinds": COLLECTION_KINDS,
            },
        )
        return [StateRollup(**row) for row in await cur.fetchall()]


# One row per state per day. `created_at` in UTC — `sourced_at` would drop runs that never
# produced a roster. Pending is included here: "still waiting" is one of a day's outcomes.
# Quiet days send no row; the strip fills its own gaps.
#
# Counted by kind as well as by outcome: `sheet_import` is most of what runs, so a day read as
# "12 ok" without saying a scraper produced none of them would mislead. Hand edits are excluded
# entirely — see COLLECTED.
STATE_CALENDAR_SQL = f"""
SELECT j.state,
       date_trunc('day', r.created_at)::date        AS day,
       count(*) FILTER (WHERE {CONFIRMED})::int     AS ok,
       count(*) FILTER (
           WHERE r.published_at IS NULL AND r.dismissed_at IS NULL
       )::int                                       AS to_review,
       count(*) FILTER (WHERE {FAILED})::int        AS failed,
       count(*) FILTER (
           WHERE r.kind = '{ChangesetKind.SCRAPE.value}'
       )::int                                       AS scrapes,
       count(*) FILTER (
           WHERE r.kind = '{ChangesetKind.SHEET_IMPORT.value}'
       )::int                                       AS imports
FROM changesets r
JOIN jurisdictions j USING (jurisdiction_ocdid)
WHERE r.created_at >= now() - %(window)s::interval
  AND {COLLECTED}
GROUP BY j.state, date_trunc('day', r.created_at)
ORDER BY j.state, day;
"""

# The localities behind one bucket, paged.
#
# `total` counts localities, not changesets, so it will NOT match the rollup — dev's `wa` is 49
# confirmed changesets across 29 places. The modal must page against this number, not that one.
#
# A CASE over three predicates because the buckets do not share a grain: `review` is the
# unwindowed queue, deduped per jurisdiction; `failed` and `ok` are windowed flows.
STATE_BUCKET_SQL = f"""
WITH rows AS (
    SELECT DISTINCT ON (r.jurisdiction_ocdid)
           r.jurisdiction_ocdid,
           j.data->>'name' AS name,
           CASE WHEN %(bucket)s = '{BUCKET_REVIEW}'
                THEN date_part('day', now() - r.sourced_at)::int END AS days_waiting,
           CASE WHEN %(bucket)s = '{BUCKET_FAILED}'
                THEN r.dismissed_reason END AS failure_reason,
           r.sourced_at,
           r.created_at
    FROM changesets r
    JOIN jurisdictions j USING (jurisdiction_ocdid)
    WHERE j.state = %(state)s
      AND CASE %(bucket)s
          WHEN '{BUCKET_REVIEW}' THEN {AVAILABLE_FOR_REVIEW}
          WHEN '{BUCKET_FAILED}' THEN {FAILED} AND r.created_at >= now() - %(window)s::interval
          WHEN '{BUCKET_OK}'     THEN {CONFIRMED} AND r.created_at >= now() - %(window)s::interval
          ELSE false
          END
    ORDER BY r.jurisdiction_ocdid, r.sourced_at DESC NULLS LAST, r.created_at DESC
)
SELECT jurisdiction_ocdid, name, days_waiting, failure_reason,
       count(*) OVER ()::int AS total
FROM rows
-- Longest-waiting first for the queue, most-recent first for the flows. The queue exists to be
-- drained oldest-end first, and burying the 90-day item on the last page defeats the bucket;
-- a flow is read newest-first because it is a record of what just happened.
ORDER BY CASE WHEN %(bucket)s = '{BUCKET_REVIEW}' THEN sourced_at END ASC NULLS LAST,
         sourced_at DESC NULLS LAST,
         name
LIMIT %(limit)s OFFSET %(offset)s;
"""


async def get_state_calendar(
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> list[CalendarDay]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            STATE_CALENDAR_SQL,
            {"window": f"{window_days} days", "collection_kinds": COLLECTION_KINDS},
        )
        return [CalendarDay(**row) for row in await cur.fetchall()]


async def get_state_bucket(
    state: str,
    bucket: str,
    limit: int,
    offset: int = 0,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> BucketPage:
    """`total` rides on each row rather than costing a second query. No rows, no total — which
    is correct, the bucket is empty."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            STATE_BUCKET_SQL,
            {
                "state": state,
                "bucket": bucket,
                "window": f"{window_days} days",
                "limit": limit,
                "offset": offset,
            },
        )
        rows = await cur.fetchall()
    # `total` rides on every row, so it is dropped before the row model sees it.
    fields = ("jurisdiction_ocdid", "name", "days_waiting", "failure_reason")
    return BucketPage(
        total=rows[0]["total"] if rows else 0,
        rows=[
            BucketRow(
                **{f: row[f] for f in fields},
                jurisdiction_path=row["jurisdiction_ocdid"],
            )
            for row in rows
        ],
    )

