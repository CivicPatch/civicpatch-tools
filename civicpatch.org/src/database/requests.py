import json
from typing import List, Optional

from psycopg import sql

from database.database import get_pool
from shared.utils.statuses import JobStatus, PullRequestStatus
from utils.github_utils import pull_request_url_to_number


async def register_request_with_job(
    request_id: str,
    job_type: str,
    arguments_json: dict,
    jurisdiction_ocdid: Optional[str] = None,
    requested_by_user_id: Optional[str] = None,
    status: JobStatus = JobStatus.PENDING,
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
            INSERT INTO jobs (
                request_id, status, progress,
                created_at, updated_at
            )
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (request_id, status, progress),
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

        # Minimal job row so the request can be looked up by its foreign request_id string
        await conn.execute(
            """
            INSERT INTO jobs (
                request_id, status, progress, created_at, updated_at
            )
            VALUES (%s, %s, 100, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (request_id, JobStatus.COMPLETED),
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


async def get_request_jurisdiction(request_id: str) -> str | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT jurisdiction_ocdid FROM requests WHERE id::text = %s",
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
        date_clauses += f" AND r.created_at >= %s"
    if to_date:
        params.append(to_date)
        date_clauses += f" AND r.created_at <= %s"

    pool = await get_pool()
    rows = []
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            sql.SQL(f"""
            SELECT r.id, r.jurisdiction_ocdid, r.created_at, r.data_json, r.review_json
            FROM requests r
            JOIN pull_requests pr ON pr.request_id = r.id
            WHERE r.jurisdiction_ocdid LIKE %s
              AND pr.status = 'open'
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
