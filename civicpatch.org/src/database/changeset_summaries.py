"""Changeset activity rolled up per state, for the cross-state summary page.

The per-jurisdiction view of the same subject is `get_jurisdiction_history`; this is the same
question one zoom level out. Where the two overlap they must agree, so the outcome is read the
same way in both: off `changesets.dismissed_reason`, the changeset's own state.
"""

import logging

from database.changesets import AVAILABLE_FOR_REVIEW
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
    RUN_LEVEL_ISSUE_TYPES,
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
BUCKET_DISMISSED = "dismissed"
BUCKET_PUBLISHED = "published"
# Sourced from `pipeline_runs`, not `changesets` — these are the attempts that proposed
# nothing, so there is no changeset for the other three buckets to have found.
BUCKET_FAILED_RUNS = "failed_runs"

# Defined once so the rollup, calendar and bucket cannot disagree. All need `changesets` as `r`.
PUBLISHED = "changesets.published_at IS NOT NULL"

# `status` too: a run that errored before recording a reason still errored.
# Only collection attempts get an outcome. A hand edit has no run to fail — 8 dev `people_edit`
# rows, none with a status — so it would land in `ok` and pad the green band with something that
# never ran. `jurisdiction_edit` is outside `AVAILABLE_FOR_REVIEW` besides, so it could never be
# "to review" and would skew one band permanently.
COLLECTED = "changesets.kind = ANY(%(collection_kinds)s)"

# Only the dismissal reason. A failed *run* no longer has a changeset to count, so this counts
# dismissed proposals; failed attempts belong to the scrape-results page, which reads runs.
DISMISSED = (
    f"changesets.dismissed_reason IN ('{DismissalReason.REJECTED.value}', "
    f"'{DismissalReason.ERRORED.value}', '{DismissalReason.CANCELLED.value}')"
)

# Each side aggregates to one row per state before joining — measured, ~114 ms at 571k
# changesets. Joining first spilled to disk. Served live; no cache.
STATE_ROLLUP_SQL = f"""
-- THE STOCK. Unwindowed: an item waiting 90 days is still waiting.
-- `AVAILABLE_FOR_REVIEW` verbatim, never a copy — a copy drifts from the pool it mirrors.
-- `DISTINCT ON` because the supersede sweep leaves transient duplicates.
WITH valid_queue AS (
    SELECT DISTINCT ON (changesets.jurisdiction_ocdid)
           changesets.jurisdiction_ocdid, changesets.updated_at
    FROM changesets
    WHERE {AVAILABLE_FOR_REVIEW}
    ORDER BY changesets.jurisdiction_ocdid, changesets.updated_at DESC
),
-- THE ATTEMPTS. Read from `pipeline_runs` directly, never through `changesets`: a run mints no
-- changeset until ingest, so a changeset-rooted join matches only runs that have already
-- finished — which is every run except the ones this is asking about.
-- Unwindowed on purpose: a run started before the window is still running, and this gates the
-- scrape button. Missing one would offer a second batch on top of a live one.
running AS (
    SELECT j.state, count(*)::int AS running
    FROM pipeline_runs pr
    JOIN jurisdictions j USING (jurisdiction_ocdid)
    WHERE pr.finished_at IS NULL
    GROUP BY j.state
),
-- Windowed, like the other flows. Attempts that died *proposing nothing* — the population that
-- appears in no changeset column at all.
--
-- Both halves of the predicate are load-bearing. `status = 'ERROR'` alone double-counts: every
-- run minted before mint-at-ingest has a changeset, and measured on dev, 9 of 10 ERROR runs are
-- already counted as `errored` there. `changeset_id IS NULL` alone catches a run that succeeded
-- and proposed nothing, which did not fail. Together they are disjoint from every proposal
-- count, so no failure is reported twice.
failed_runs AS (
    SELECT j.state, count(*)::int AS failed_runs
    FROM pipeline_runs pr
    JOIN jurisdictions j USING (jurisdiction_ocdid)
    WHERE pr.created_at >= now() - %(window)s::interval
      AND pr.status = '{PipelineRunStatus.ERROR.value}'
      AND pr.changeset_id IS NULL
    GROUP BY j.state
),
queue AS (
    SELECT j.state,
           count(*)::int                                    AS to_review,
           max(date_part('day', now() - q.updated_at))::int AS oldest_days
    FROM valid_queue q
    JOIN jurisdictions j USING (jurisdiction_ocdid)
    GROUP BY j.state
),
-- THE FLOWS. Windowed events; pending belongs to the queue above.
-- A dismissal with no reason falls through every FILTER, which is the honest answer.
flows AS (
    SELECT j.state,
           count(*) FILTER (WHERE {PUBLISHED})::int AS published,
           -- `FAILED` verbatim, the same predicate `get_state_bucket` lists by. Counting the
           -- reasons separately here is what let the two drift: the list included `cancelled`
           -- and the count did not, so the badge promised fewer rows than the bucket showed —
           -- 12 of them in 30 days, measured on dev.
           count(*) FILTER (WHERE {DISMISSED})::int AS dismissed,
           max(changesets.created_at) AS last_run_at
    FROM changesets
    JOIN jurisdictions j USING (jurisdiction_ocdid)
    WHERE changesets.created_at >= now() - %(window)s::interval
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
    COALESCE(f.published, 0)    AS published,
    COALESCE(f.dismissed, 0)    AS dismissed,
    COALESCE(e.roster_edits, 0) AS roster_edits,
    COALESCE(rn.running, 0)     AS running,
    COALESCE(fr.failed_runs, 0) AS failed_runs,
    f.last_run_at
FROM (SELECT DISTINCT state FROM jurisdictions) j
LEFT JOIN running rn USING (state)
LEFT JOIN failed_runs fr USING (state)
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


# One row per state per day. `created_at` in UTC — `updated_at` would drop runs that never
# produced a roster. Pending is included here: "still waiting" is one of a day's outcomes.
# Quiet days send no row; the strip fills its own gaps.
#
# Counted by kind as well as by outcome: `sheet_import` is most of what runs, so a day read as
# "12 published" without saying a scraper produced none of them would mislead. Hand edits are excluded
# entirely — see COLLECTED.
STATE_CALENDAR_SQL = f"""
SELECT j.state,
       date_trunc('day', changesets.created_at)::date        AS day,
       count(*) FILTER (WHERE {PUBLISHED})::int     AS published,
       count(*) FILTER (
           WHERE changesets.published_at IS NULL AND changesets.dismissed_at IS NULL
       )::int                                       AS to_review,
       count(*) FILTER (WHERE {DISMISSED})::int        AS dismissed,
       count(*) FILTER (
           WHERE changesets.kind = '{ChangesetKind.SCRAPE.value}'
       )::int                                       AS scrapes,
       count(*) FILTER (
           WHERE changesets.kind = '{ChangesetKind.SHEET_IMPORT.value}'
       )::int                                       AS imports
FROM changesets
JOIN jurisdictions j USING (jurisdiction_ocdid)
WHERE changesets.created_at >= now() - %(window)s::interval
  AND {COLLECTED}
GROUP BY j.state, date_trunc('day', changesets.created_at)
ORDER BY j.state, day;
"""

# The localities behind one bucket, paged.
#
# `total` counts localities, not changesets, so it will NOT match the rollup — dev's `wa` is 49
# published changesets across 29 places. The modal must page against this number, not that one.
#
# A CASE over three predicates because the buckets do not share a grain: `review` is the
# unwindowed queue, deduped per jurisdiction; `dismissed` and `published` are windowed flows.
STATE_BUCKET_SQL = f"""
WITH rows AS (
    SELECT DISTINCT ON (changesets.jurisdiction_ocdid)
           changesets.jurisdiction_ocdid,
           j.data->>'name' AS name,
           CASE WHEN %(bucket)s = '{BUCKET_REVIEW}'
                THEN date_part('day', now() - changesets.updated_at)::int END AS days_waiting,
           CASE WHEN %(bucket)s = '{BUCKET_DISMISSED}'
                THEN changesets.dismissed_reason END AS failure_reason,
           changesets.updated_at,
           changesets.created_at
    FROM changesets
    JOIN jurisdictions j USING (jurisdiction_ocdid)
    WHERE j.state = %(state)s
      AND CASE %(bucket)s
          WHEN '{BUCKET_REVIEW}' THEN {AVAILABLE_FOR_REVIEW}
          WHEN '{BUCKET_DISMISSED}' THEN {DISMISSED} AND changesets.created_at >= now() - %(window)s::interval
          WHEN '{BUCKET_PUBLISHED}' THEN {PUBLISHED} AND changesets.created_at >= now() - %(window)s::interval
          ELSE false
          END
    ORDER BY changesets.jurisdiction_ocdid, changesets.updated_at DESC NULLS LAST, changesets.created_at DESC
)
SELECT jurisdiction_ocdid, name, days_waiting, failure_reason,
       count(*) OVER ()::int AS total
FROM rows
-- Longest-waiting first for the queue, most-recent first for the flows. The queue exists to be
-- drained oldest-end first, and burying the 90-day item on the last page defeats the bucket;
-- a flow is read newest-first because it is a record of what just happened.
ORDER BY CASE WHEN %(bucket)s = '{BUCKET_REVIEW}' THEN updated_at END ASC NULLS LAST,
         updated_at DESC NULLS LAST,
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


# The failed-run bucket cannot be a fourth branch of STATE_BUCKET_SQL: that reads `changesets`,
# and the whole point of this population is that it has none. Same output shape, so the bucket
# component renders it unchanged.
STATE_FAILED_RUNS_SQL = f"""
WITH rows AS (
    SELECT DISTINCT ON (pr.jurisdiction_ocdid)
           pr.jurisdiction_ocdid,
           j.data->>'name' AS name,
           NULL::int AS days_waiting,
           -- Why it ended, keyed on the run: a run that mints no changeset has its issue
           -- filed against its own id.
           i.issue_type AS failure_reason,
           pr.created_at
    FROM pipeline_runs pr
    JOIN jurisdictions j USING (jurisdiction_ocdid)
    LEFT JOIN issues i ON i.issue_key = pr.id::text AND i.issue_type = ANY(%(issue_types)s)
    WHERE j.state = %(state)s
      AND pr.created_at >= now() - %(window)s::interval
      AND pr.status = '{PipelineRunStatus.ERROR.value}'
      AND pr.changeset_id IS NULL
    ORDER BY pr.jurisdiction_ocdid, pr.created_at DESC
)
SELECT jurisdiction_ocdid, name, days_waiting, failure_reason,
       count(*) OVER ()::int AS total
FROM rows
-- Newest first: a record of what just happened, like the other flows.
ORDER BY created_at DESC, name
LIMIT %(limit)s OFFSET %(offset)s;
"""


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
        params = {
            "state": state,
            "window": f"{window_days} days",
            "limit": limit,
            "offset": offset,
        }
        if bucket == BUCKET_FAILED_RUNS:
            await cur.execute(
                STATE_FAILED_RUNS_SQL,
                {**params, "issue_types": list(RUN_LEVEL_ISSUE_TYPES)},
            )
        else:
            await cur.execute(STATE_BUCKET_SQL, {**params, "bucket": bucket})
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

