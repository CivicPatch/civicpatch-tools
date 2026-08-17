import json
from typing import List, Optional

from psycopg import sql

from database.database import get_pool
from shared.utils.statuses import (
    PipelineIssueStatus,
    PipelineIssueType,
    PipelineRunStatus,
    PullRequestStatus,
    RequestReviewStatus,
    RequestType,
)
from lib.github.utils import pull_request_url_to_number

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

# SQL predicate for "a scrape still awaiting human review". Requires the requests table to be
# aliased `r`; callers share this one definition instead of re-spelling it.
#
# Publish state used to live on GitHub — an open PR that had not been parked for merge — so
# this was a JOIN against pull_requests. Migration 115 moved it onto the request itself, which
# is where it belongs now that civicpatch publishes rather than waiting for a merge.
#
# Five conditions:
#   the run succeeded        see below — this one is new
#   not published            was pr.status='open' + pr.merge_enqueued_at IS NULL
#   not dismissed            was pr.status='closed'
#   not a jurisdiction edit  same, but a plain column test now the anchor is `requests`
#   no live reviewer-reported issue   unchanged; returns to the pool when the issue is
#                                     resolved by an admin or superseded by a newer run
#
# The success test is new because the PR gate had been standing in for it: a pull request only
# ever existed if data_intake received a roster, so cancelled and errored runs were filtered out
# as a side effect of requiring one. Without it they become cards with nothing to review —
# measured 2026-08-17, 10 CANCELLED + 7 ERROR, every one with a NULL data_json.
#
# Written as EXISTS rather than a `j.status` test so the predicate stays anchored on `r` alone:
# not every caller joins pipeline_runs, and requiring one is a trap for the next site added.
AVAILABLE_FOR_REVIEW = (
    "EXISTS ("
    "SELECT 1 FROM pipeline_runs j_ok "
    f"WHERE j_ok.request_id = r.id AND j_ok.status = '{PipelineRunStatus.SUCCESS.value}'"
    ") "
    "AND r.published_at IS NULL AND r.dismissed_at IS NULL "
    f"AND r.request_type != '{RequestType.JURISDICTION_MANUAL_EDIT.value}' "
    "AND NOT EXISTS ("
    "SELECT 1 FROM issues i "
    f"WHERE i.issue_type = '{PipelineIssueType.USER_REPORTED.value}' "
    "AND r.id::text = ANY(i.request_ids) "
    f"AND i.status NOT IN ('{PipelineIssueStatus.RESOLVED.value}', '{PipelineIssueStatus.SUPERSEDED.value}')"
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
            INSERT INTO requests (id, request_type, jurisdiction_ocdid, arguments_json, requested_by_user_id, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (request_id, job_type, jurisdiction_ocdid, json.dumps(arguments_json), requested_by_user_id),
        )

        await conn.execute(
            """
            INSERT INTO pipeline_runs (
                request_id, status, progress,
                created_at, updated_at
            )
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (request_id, status, progress),
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
            INSERT INTO requests (id, request_type, jurisdiction_ocdid, arguments_json, created_at, updated_at)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (id) DO NOTHING
            """,
            (request_id, job_type, jurisdiction_ocdid, json.dumps(arguments_json)),
        )
        await conn.execute(
            """
            INSERT INTO pipeline_runs (request_id, status, progress, created_at, updated_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (request_id) DO NOTHING
            """,
            (request_id, PipelineRunStatus.PENDING, 0),
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
            INSERT INTO requests (id, request_type, jurisdiction_ocdid, created_at, updated_at)
            VALUES (%s, 'people', %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (request_id, jurisdiction_ocdid),
        )

        # Minimal pipeline_run row so the request can be looked up by its foreign request_id string
        await conn.execute(
            """
            INSERT INTO pipeline_runs (
                request_id, status, progress, created_at, updated_at
            )
            VALUES (%s, %s, 100, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (request_id, PipelineRunStatus.SUCCESS),
        )

        pr_number = 0
        if pr_url:
            num = pull_request_url_to_number(pr_url)
            pr_number = int(num) if num else 0

        await conn.execute(
            """
            INSERT INTO pull_requests (request_id, url, status, pr_number, created_at, updated_at)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (request_id, pr_url, PullRequestStatus.OPEN, pr_number),
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
                open_data_url, published_at, resolved_by_user_id, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, now(), %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
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
                   COALESCE(r.data_json, '[]'::jsonb) AS data_json,
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
            "data_json": r[3] or [],
            "jurisdiction_name": r[4],
        }
        for r in rows
    ]


async def get_requests_for_export(
    state: str,
    from_date: str | None,
    to_date: str | None,
) -> list[dict]:
    state_prefix = f"ocd-jurisdiction/country:us/state:{state.lower()}%"
    params: list = [state_prefix]
    date_clauses = ""
    if from_date:
        params.append(from_date)
        date_clauses += " AND r.created_at >= %s"
    if to_date:
        params.append(to_date)
        date_clauses += " AND r.created_at <= %s"

    pool = await get_pool()
    rows = []
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            sql.SQL(f"""
            SELECT r.id, r.jurisdiction_ocdid, r.created_at, r.data_json, r.review_json
            FROM requests r
            WHERE r.jurisdiction_ocdid LIKE %s
              AND r.published_at IS NULL AND r.dismissed_at IS NULL
              {date_clauses}
            ORDER BY r.created_at DESC
            """),
            params,
        )
        while True:
            batch = await cur.fetchmany(200)
            if not batch:
                break
            rows.extend(batch)
    return [
        {
            "request_id": str(r[0]),
            "jurisdiction_ocdid": r[1],
            "created_at": r[2].isoformat() if r[2] else None,
            "data_json": r[3] or [],
            "review_json": r[4] or {},
        }
        for r in rows
    ]
