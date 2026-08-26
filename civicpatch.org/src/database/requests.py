import json
from datetime import timedelta
from typing import Optional

from database.database import get_pool
from database.review_sessions import (
    SESSION_IDLE_TIMEOUT_MINUTES,
    ReviewSessionEntryStatus,
)
from shared.utils.statuses import (
    TERMINAL_PIPELINE_RUN_STATUSES,
    PipelineIssueStatus,
    PipelineIssueType,
    PipelineRunStatus,
    RequestReviewStatus,
    RequestType,
)

# The review lifecycle as one SQL expression, so the sites that render it cannot drift apart.
# Requires the requests table aliased `r`, like AVAILABLE_FOR_REVIEW below.
#
# Derived, not stored: the two timestamps are the state, and a CHECK forbids both being set.
# It replaces `pull_requests.status`, which had to distinguish open from merged because the
# publish happened on GitHub. Nothing merges now, so there are three answers, not four.
REVIEW_STATUS = (
    "CASE "
    f"WHEN r.published_at IS NOT NULL THEN '{RequestReviewStatus.PUBLISHED.value}' "
    f"WHEN r.dismissed_at IS NOT NULL THEN '{RequestReviewStatus.DISMISSED.value}' "
    f"ELSE '{RequestReviewStatus.PENDING.value}' END"
)

# SQL predicate for "this jurisdiction already has work in flight" — the scrape-candidate gate.
# Requires the requests table aliased `r`.
#
# Two things count: a run that has not finished, and a finished one still waiting to be
# reviewed. A run that ended without producing anything does NOT — an errored or cancelled
# scrape is over, and blocking on it would make a jurisdiction un-scrapeable until someone
# dismissed a request that was never reviewable.
#
# That last clause is why this cannot simply be "unpublished and undismissed": cancelling
# leaves both timestamps NULL, so the plain test never lets go.
WORK_IN_FLIGHT = (
    "r.published_at IS NULL AND r.dismissed_at IS NULL "
    f"AND r.request_type != '{RequestType.JURISDICTION_MANUAL_EDIT.value}' "
    f"AND r.status NOT IN ('{PipelineRunStatus.ERROR.value}', "
    f"'{PipelineRunStatus.CANCELLED.value}', '{PipelineRunStatus.RESOLVED.value}') "
    "AND r.status IS NOT NULL"
)

# Why a request left the pool. `dismissed_at` says only that it did.
DISMISSED_SUPERSEDED = "superseded"
DISMISSED_UNCHANGED = "unchanged"

# SQL predicate for "a scrape still awaiting human review". Requires the requests table to be
# aliased `r`; callers share this one definition instead of re-spelling it.
#
AVAILABLE_FOR_REVIEW = (
    "EXISTS (SELECT 1 FROM source_records sr WHERE sr.request_id = r.id) "
    "AND r.published_at IS NULL AND r.dismissed_at IS NULL "
    f"AND r.request_type != '{RequestType.JURISDICTION_MANUAL_EDIT.value}' "
    "AND NOT EXISTS ("
    "SELECT 1 FROM issues i "
    f"WHERE i.issue_type = '{PipelineIssueType.USER_REPORTED.value}' "
    "AND r.id::text = ANY(i.request_ids) "
    f"AND i.status NOT IN ('{PipelineIssueStatus.RESOLVED.value}', '{PipelineIssueStatus.SUPERSEDED.value}')"
    ")"
)

# Is the scrape still going? Derived here for the same reason `REVIEW_STATUS` is: the answer
# is a fact about the run, and every caller that recomputed it had to know which statuses count
# as terminal — a set that was defined twice, once in Python and once in the frontend.
#
# `status IS NULL` is a request no pipeline ever ran — a jurisdiction edit, or a roster
# typed in rather than scraped — which is not in flight.
RUN_IN_FLIGHT = (
    "r.status IS NOT NULL AND r.status != ALL(ARRAY["
    + ", ".join(f"'{status.value}'" for status in TERMINAL_PIPELINE_RUN_STATUSES)
    + "])"
)

# Request supercede can dismiss.
# Sweep should not dismiss a card still in the queue.
SWEEPABLE = (
    f"{AVAILABLE_FOR_REVIEW} "
    "AND EXISTS ("
    "SELECT 1 FROM jurisdictions j "
    "WHERE j.jurisdiction_ocdid = r.jurisdiction_ocdid "
    "AND j.status = 'active'"
    ")"
)

HELD_BY_REVIEWER = (
    "EXISTS ("
    "SELECT 1 FROM review_session_entries e "
    "WHERE r.id::text = ANY(e.request_ids) "
    f"AND (e.status IN ('{ReviewSessionEntryStatus.SAVED}', '{ReviewSessionEntryStatus.RESOLVED}') "
    f"OR (e.status = '{ReviewSessionEntryStatus.CLAIMED}' AND e.created_at >= NOW() - %s))"
    ")"
)


async def register_request_with_pipeline_run(
    request_id: str,
    job_type: str,
    arguments_json: dict,
    jurisdiction_ocdid: Optional[str] = None,
    requested_by_user_id: Optional[str] = None,
    status: PipelineRunStatus = PipelineRunStatus.PENDING,
    progress: int = 0,
):
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO requests (id, request_type, jurisdiction_ocdid, arguments_json, requested_by_user_id, created_at)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """,
            (
                request_id,
                job_type,
                jurisdiction_ocdid,
                json.dumps(arguments_json),
                requested_by_user_id,
            ),
        )

        await conn.execute(
            """
            UPDATE requests SET status = %s, progress = %s,
                                sourced_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (status, progress, request_id),
        )


async def register_request_with_pipeline_run_if_not_exists(
    request_id: str,
    job_type: str,
    arguments_json: dict,
    jurisdiction_ocdid: Optional[str] = None,
):
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO requests (id, request_type, jurisdiction_ocdid, arguments_json, created_at)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (id) DO NOTHING
            """,
            (request_id, job_type, jurisdiction_ocdid, json.dumps(arguments_json)),
        )
        await conn.execute(
            """
            UPDATE requests SET status = %s, progress = %s,
                                sourced_at = CURRENT_TIMESTAMP
            WHERE id = %s AND status IS NULL
            """,
            (PipelineRunStatus.PENDING, 0, request_id),
        )


async def register_foreign_request(
    request_id: str,
    jurisdiction_ocdid: str,
    pr_url: Optional[str],
    provider: str,
):
    """
    Create a request + pull_request record for a PR that has no backing job worker.
    The request_id is "foreign" — derived from the git branch name, not our job pipeline.
    Used by the GitHub webhook handler and hourly PR sync.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO requests (id, request_type, jurisdiction_ocdid, created_at)
            VALUES (%s, 'people', %s, CURRENT_TIMESTAMP)
            """,
            (request_id, jurisdiction_ocdid),
        )

        # No pipeline ran — the id comes off a git branch. Stamped SUCCESS because the work
        # is already done elsewhere; before the merge this needed a whole fabricated run row.
        await conn.execute(
            """
            UPDATE requests SET status = %s, progress = 100,
                                sourced_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (PipelineRunStatus.SUCCESS, request_id),
        )



async def register_jurisdiction_edit_request(
    request_id: str,
    jurisdiction_ocdid: str,
    arguments_json: dict,
    open_data_url: str,
    requested_by_user_id: Optional[str] = None,
):
    """Track a hand-edited jurisdiction field as a request.

    Born published: the edit is committed before this is called, so there is no interval
    during which it is pending. That is the whole difference from a scrape, which is
    proposed and then reviewed.

    No pipeline_run: nothing ran. That keeps it out of the scrape history, which is
    joined through pipeline_runs, and out of anything that assumes a job produced it.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO requests (
                id, request_type, jurisdiction_ocdid, arguments_json, requested_by_user_id,
                open_data_url, published_at, resolved_by_user_id, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, now(), %s, CURRENT_TIMESTAMP)
            """,
            (
                request_id,
                RequestType.JURISDICTION_MANUAL_EDIT,
                jurisdiction_ocdid,
                json.dumps(arguments_json),
                requested_by_user_id,
                open_data_url,
                requested_by_user_id,
            ),
        )


async def get_request_jurisdiction(request_id: str) -> str | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT jurisdiction_ocdid FROM requests WHERE id::text = %s",
            (request_id,),
        )
        row = await cur.fetchone()
    return row[0] if row else None


async def jurisdictions_for_requests(request_ids: list[str]) -> dict[str, str]:
    """Which jurisdiction each request is about. The roster itself is derived from that
    request's sightings, so this is all a caller needs to ask for one."""
    if not request_ids:
        return {}
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id::text, jurisdiction_ocdid FROM requests WHERE id::text = ANY(%s)",
            (request_ids,),
        )
        return {request_id: ocdid for request_id, ocdid in await cur.fetchall()}


async def get_request_type(request_id: str) -> str | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT request_type FROM requests WHERE id::text = %s",
            (request_id,),
        )
        row = await cur.fetchone()
    return row[0] if row else None


async def get_issue_request_details(request_ids: list[str]) -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT r.id::text, r.jurisdiction_ocdid, r.arguments_json,
                   COALESCE(j.data->>'name', r.jurisdiction_ocdid) AS jurisdiction_name
            FROM requests r
            LEFT JOIN jurisdictions j ON j.jurisdiction_ocdid = r.jurisdiction_ocdid
            WHERE r.id::text = ANY(%s)
            ORDER BY r.created_at
            """,
            (request_ids,),
        )
        rows = await cur.fetchall()
    return [
        {
            "request_id": r[0],
            "jurisdiction_ocdid": r[1],
            "arguments_json": r[2] or {},
            "jurisdiction_name": r[3],
        }
        for r in rows
    ]


async def dismiss_as_unchanged(cur, request_id: str) -> bool:
    """Retire a scrape that asserted nothing new. Returns whether it was still open.

    Guarded in the statement rather than by checking first: a reviewer may be publishing this
    very request, and losing that race must not overwrite their decision.
    """
    await cur.execute(
        f"""
        UPDATE requests
           SET dismissed_at = now(), dismissed_reason = '{DISMISSED_UNCHANGED}'
         WHERE id::text = %s AND published_at IS NULL AND dismissed_at IS NULL
        """,
        (request_id,),
    )
    return cur.rowcount > 0


async def supersede_stacked_requests() -> list[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            -- Ordered by `sourced_at`: which scrape read the source more recently, never
            -- which row was touched more recently. A reviewer editing an old roster did not go
            -- and look again. Work in progress is protected by the held-card exclusion
            -- instead, which is time-boxed on purpose.
            --
            -- `sourced_at IS NOT NULL`, so a request with no run cannot supersede or be
            -- superseded. That is jurisdiction edits (already excluded by `SWEEPABLE`) and,
            -- once it exists, anything typed in rather than scraped.
            WITH candidates AS (
                SELECT r.id, r.jurisdiction_ocdid, r.sourced_at
                FROM requests r
                WHERE {SWEEPABLE} AND NOT {HELD_BY_REVIEWER}
                  AND r.sourced_at IS NOT NULL
            ),
            -- What can supersede, which is not the same set as what can BE superseded: a
            -- published request is no longer a candidate, so comparing candidates only to each
            -- other left every draft older than a publish in the pool forever.
            --
            -- Built from `candidates`, not re-queried: that inherits the held-card exclusion,
            -- and it must. A reviewer holding the newest card shields the whole jurisdiction
            -- for the pass — sweep the older ones and their rejecting it strands the lot.
            supersedors AS (
                SELECT jurisdiction_ocdid, sourced_at FROM candidates
                UNION ALL
                SELECT r.jurisdiction_ocdid, r.sourced_at
                FROM requests r
                WHERE r.published_at IS NOT NULL AND r.sourced_at IS NOT NULL
            )
            UPDATE requests
               SET dismissed_at = now(), dismissed_reason = '{DISMISSED_SUPERSEDED}'
             WHERE id IN (
                 SELECT older.id
                 FROM candidates older
                 WHERE EXISTS (
                     SELECT 1 FROM supersedors newer
                     WHERE newer.jurisdiction_ocdid = older.jurisdiction_ocdid
                       AND newer.sourced_at > older.sourced_at
                 )
             )
            RETURNING id::text
            """,
            (timedelta(minutes=SESSION_IDLE_TIMEOUT_MINUTES),),
        )
        return [row[0] for row in await cur.fetchall()]
