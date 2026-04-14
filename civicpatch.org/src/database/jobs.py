import json
from collections import Counter
from typing import Any, List, Optional

from psycopg import sql

from database.database import get_pool, to_iso
from shared.utils.statuses import TERMINAL_JOB_STATUSES
from lib.github.utils import pull_request_url_to_number

async def get_duplicate_jurisdiction_ocdids() -> set:
    """Return a set of jurisdiction_ocdids that appear in more than one open PR."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT r.jurisdiction_ocdid
            FROM jobs j
            JOIN requests r ON r.id = j.request_id
            JOIN pull_requests pr ON pr.request_id = r.id
            WHERE pr.status = 'open'
            """
        )
        rows = await cur.fetchall()
    ocdids = [r[0] for r in rows if r[0]]
    counts = Counter(ocdids)
    return {ocdid for ocdid, count in counts.items() if count > 1}

async def get_stale_duplicate_pr_info() -> list[dict]:
    """
    For each jurisdiction with more than one open PR, return all but the latest
    (by job created_at). Used for bulk-closing stale duplicates.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            WITH ranked AS (
                SELECT
                    j.request_id,
                    pr.pr_number,
                    ROW_NUMBER() OVER (
                        PARTITION BY r.jurisdiction_ocdid ORDER BY j.created_at DESC
                    ) AS rn
                FROM jobs j
                JOIN requests r ON r.id = j.request_id
                JOIN pull_requests pr ON pr.request_id = r.id
                WHERE pr.status = 'open'
                  AND r.jurisdiction_ocdid IN (
                      SELECT r2.jurisdiction_ocdid
                      FROM jobs j2
                      JOIN requests r2 ON r2.id = j2.request_id
                      JOIN pull_requests pr2 ON pr2.request_id = r2.id
                      WHERE pr2.status = 'open'
                      GROUP BY r2.jurisdiction_ocdid
                      HAVING COUNT(*) > 1
                  )
            )
            SELECT request_id, pr_number FROM ranked WHERE rn > 1
            """
        )
        rows = await cur.fetchall()
    return [{"request_id": r[0], "pr_number": r[1]} for r in rows]


async def get_job_for_review(request_id: str) -> dict | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT pr.url, pr.status, pr.review_state,
                   r.jurisdiction_ocdid,
                   jur.data->>'name' AS jurisdiction_name,
                   j.created_at, j.updated_at
            FROM jobs j
            JOIN requests r ON r.id = j.request_id
            LEFT JOIN pull_requests pr ON pr.request_id = j.request_id
            LEFT JOIN jurisdictions jur ON jur.jurisdiction_ocdid = r.jurisdiction_ocdid
            WHERE j.request_id = %s
            """,
            (request_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "request_id": request_id,
            "pull_request_url": row[0],
            "pull_request_status": row[1],
            "pull_request_review_state": row[2],
            "jurisdiction_ocdid": row[3],
            "jurisdiction_name": row[4],
            "created_at": to_iso(row[5]),
            "updated_at": to_iso(row[6]),
        }


async def list_jobs():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT request_id, status, progress, created_at, updated_at FROM jobs
            ORDER BY created_at DESC;
            """,
        )
        rows = await cur.fetchall()
        jobs = []
        for row in rows:
            jobs.append(
                {
                    "request_id": row[0],
                    "status": row[1],
                    "progress": row[2],
                    "created_at": row[3],
                    "updated_at": row[4],
                }
            )
    return jobs


async def get_job(request_id: str):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT j.status, j.progress, r.arguments_json, r.data_json,
                   j.created_at, j.updated_at, pr.url
            FROM jobs j
            LEFT JOIN requests r ON r.id = j.request_id
            LEFT JOIN pull_requests pr ON pr.request_id = r.id
            WHERE j.request_id = %s;
            """,
            (request_id,),
        )
        row = await cur.fetchone()
        if row:
            return {
                "request_id": request_id,
                "status": row[0],
                "progress": row[1],
                "arguments_json": row[2],
                "data_json": row[3],
                "created_at": to_iso(row[4]),
                "updated_at": to_iso(row[5]),
                "pull_request_url": row[6],
            }
        return None


async def set_job_github_run_id(request_id: str, github_run_id: int) -> bool:
    pool = await get_pool()
    async with pool.connection() as conn:
        result = await conn.execute(
            "UPDATE jobs SET github_run_id = %s WHERE request_id = %s",
            (github_run_id, request_id),
        )
        return result.rowcount > 0


async def get_active_job_jurisdiction_ocdids() -> set[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT DISTINCT r.jurisdiction_ocdid
            FROM jobs j
            JOIN requests r ON r.id = j.request_id
            WHERE j.status != ALL(%s)
            AND r.jurisdiction_ocdid IS NOT NULL
            """,
            (list(TERMINAL_JOB_STATUSES),),
        )
        rows = await cur.fetchall()
        return {row[0] for row in rows}


async def get_active_jobs(state_code: Optional[str] = None, page: int = 1, per_page: int = 25) -> tuple[list[dict], int]:
    pool = await get_pool()
    offset = (page - 1) * per_page
    async with pool.connection() as conn, conn.cursor() as cur:
        query = """
            SELECT j.request_id, j.status, j.progress, j.created_at, j.updated_at,
                   r.jurisdiction_ocdid, jur.state, jur.data->>'name',
                   COUNT(*) OVER() AS total_count
            FROM jobs j
            JOIN requests r ON r.id = j.request_id
            JOIN jurisdictions jur ON jur.jurisdiction_ocdid = r.jurisdiction_ocdid
            WHERE j.status != ALL(%s)
            AND r.jurisdiction_ocdid IS NOT NULL
            AND r.request_type = 'people'
        """
        params: list = [list(TERMINAL_JOB_STATUSES)]
        if state_code:
            query += " AND jur.state = %s"
            params.append(state_code.lower())
        query += " ORDER BY j.updated_at DESC LIMIT %s OFFSET %s"
        params.extend([per_page, offset])
        await cur.execute(query, params)
        rows = await cur.fetchall()
        total = rows[0][8] if rows else 0
        return [
            {
                "request_id": row[0],
                "status": row[1],
                "progress": row[2],
                "created_at": to_iso(row[3]),
                "updated_at": to_iso(row[4]),
                "jurisdiction_ocdid": row[5],
                "state": row[6],
                "jurisdiction_name": row[7],
            }
            for row in rows
        ], total


async def get_job_github_run_id(request_id: str) -> int | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT github_run_id FROM jobs WHERE request_id = %s",
            (request_id,),
        )
        row = await cur.fetchone()
        return row[0] if row else None


async def get_job_status(request_id: str):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT status, progress FROM jobs
            WHERE request_id = %s;
            """,
            (request_id,),
        )
        row = await cur.fetchone()
        if row:
            return {"request_id": request_id, "status": row[0], "progress": row[1]}
        return None


async def update_job_status(request_id: str, status: str | None = None, progress: Optional[int] = None):
    pool = await get_pool()
    set_clauses = []
    params = []

    if progress is not None:
        set_clauses.append("progress = %s")
        params.append(progress)
    if status is not None:
        set_clauses.append("status = %s")
        params.append(status)

    set_clauses.append("updated_at = CURRENT_TIMESTAMP")

    if not set_clauses:
        return

    params.append(request_id)
    set_clause_str = ", ".join(set_clauses)

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            sql.SQL(f"""
            UPDATE jobs
            SET {set_clause_str}
            WHERE request_id = %s;
            """),
            params,
        )


async def update_job_data(request_id: str, data_json: Any):
    pool = await get_pool()
    async with pool.connection() as conn:
        result = await conn.execute(
            """
            UPDATE requests r
            SET data_json = %s,
                updated_at = CURRENT_TIMESTAMP
            FROM jobs j
            WHERE r.id = j.request_id AND j.request_id = %s;
            """,
            (
                json.dumps(data_json),
                request_id,
            ),
        )
        if result.rowcount == 0:
            return False
        return True


async def update_job_review_json(request_id: str, review_json: dict):
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            UPDATE requests r
            SET review_json = %s,
                updated_at = CURRENT_TIMESTAMP
            FROM jobs j
            WHERE r.id = j.request_id AND j.request_id = %s;
            """,
            (json.dumps(review_json), request_id),
        )


async def get_job_data_json(request_id: str):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT r.data_json
            FROM jobs j
            LEFT JOIN requests r ON r.id = j.request_id
            WHERE j.request_id = %s LIMIT 1
            """,
            (request_id,),
        )
        row = await cur.fetchone()
    return row[0] if row else None


async def get_job_result(request_id: str):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT r.data_json, r.review_json FROM requests r
            JOIN jobs j ON j.request_id = r.id
            WHERE j.request_id = %s LIMIT 1
            """,
            (request_id,),
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return {"data": row[0], "review_json": row[1]}


