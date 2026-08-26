from datetime import datetime, timedelta
from typing import Optional

from database.database import get_pool, to_iso
from psycopg import sql
from shared.utils.statuses import TERMINAL_PIPELINE_RUN_STATUSES


async def run_updated_at(cur, request_id: str) -> datetime:
    """`pipeline_runs.updated_at` — when the run last reported its status.

    Stamped by the pipeline's own report, not at ingest, which can be hours later on a retry or
    a replayed artifact.
    """
    await cur.execute(
        "SELECT updated_at FROM pipeline_runs WHERE request_id::text = %s",
        (request_id,),
    )
    row = await cur.fetchone()
    if row is None:
        raise ValueError(f"No pipeline run for request {request_id}")
    return row[0]


async def list_pipeline_runs():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT request_id, status, progress, created_at, updated_at FROM pipeline_runs
            ORDER BY created_at DESC;
            """,
        )
        rows = await cur.fetchall()
        pipeline_runs = []
        for row in rows:
            pipeline_runs.append(
                {
                    "request_id": row[0],
                    "status": row[1],
                    "progress": row[2],
                    "created_at": row[3],
                    "updated_at": row[4],
                }
            )
    return pipeline_runs


async def get_pipeline_run(request_id: str):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT j.status, j.progress, r.arguments_json,
                   j.created_at, j.updated_at, r.open_data_url
            FROM pipeline_runs j
            LEFT JOIN requests r ON r.id = j.request_id
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
                "created_at": to_iso(row[3]),
                "updated_at": to_iso(row[4]),
                "pull_request_url": row[5],
            }
        return None


async def set_pipeline_run_github_run_id(request_id: str, github_run_id: int) -> bool:
    pool = await get_pool()
    async with pool.connection() as conn:
        result = await conn.execute(
            "UPDATE pipeline_runs SET github_run_id = %s WHERE request_id = %s",
            (github_run_id, request_id),
        )
        return result.rowcount > 0


async def get_active_pipeline_run_jurisdiction_ocdids() -> set[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT DISTINCT r.jurisdiction_ocdid
            FROM pipeline_runs j
            JOIN requests r ON r.id = j.request_id
            WHERE j.status != ALL(%s)
            AND r.jurisdiction_ocdid IS NOT NULL
            """,
            (list(TERMINAL_PIPELINE_RUN_STATUSES),),
        )
        rows = await cur.fetchall()
        return {row[0] for row in rows}


async def get_active_pipeline_run_jurisdiction_ocdids_by_state(
    state_code: str,
) -> set[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT DISTINCT r.jurisdiction_ocdid
            FROM pipeline_runs j
            JOIN requests r ON r.id = j.request_id
            WHERE j.status != ALL(%s)
            AND r.jurisdiction_ocdid LIKE %s
            """,
            (list(TERMINAL_PIPELINE_RUN_STATUSES), f"%state:{state_code}%"),
        )
        rows = await cur.fetchall()
        return {row[0] for row in rows}


async def get_active_pipeline_runs(
    state_code: Optional[str] = None, page: int = 1, per_page: int = 25
) -> tuple[list[dict], int]:
    pool = await get_pool()
    offset = (page - 1) * per_page
    async with pool.connection() as conn, conn.cursor() as cur:
        query = """
            SELECT j.request_id, j.status, j.progress, j.created_at, j.updated_at,
                   r.jurisdiction_ocdid, jur.state, jur.data->>'name',
                   COUNT(*) OVER() AS total_count
            FROM pipeline_runs j
            JOIN requests r ON r.id = j.request_id
            JOIN jurisdictions jur ON jur.jurisdiction_ocdid = r.jurisdiction_ocdid
            WHERE j.status != ALL(%s)
            AND r.jurisdiction_ocdid IS NOT NULL
            AND r.request_type = 'people'
        """
        params: list = [list(TERMINAL_PIPELINE_RUN_STATUSES)]
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


async def get_pipeline_run_github_run_id(request_id: str) -> int | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT github_run_id FROM pipeline_runs WHERE request_id = %s",
            (request_id,),
        )
        row = await cur.fetchone()
        return row[0] if row else None


async def get_pipeline_run_status(request_id: str):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT status, progress FROM pipeline_runs
            WHERE request_id = %s;
            """,
            (request_id,),
        )
        row = await cur.fetchone()
        if row:
            return {"request_id": request_id, "status": row[0], "progress": row[1]}
        return None


async def update_pipeline_run_status(
    request_id: str, status: str | None = None, progress: Optional[int] = None
):
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
            UPDATE pipeline_runs
            SET {set_clause_str}
            WHERE request_id = %s;
            """),
            params,
        )


RUN_NOT_TERMINAL = (
    "pipeline_runs.status IS NOT NULL AND pipeline_runs.status != ALL(ARRAY["
    + ", ".join(f"'{status.value}'" for status in TERMINAL_PIPELINE_RUN_STATUSES)
    + "])"
)


async def expire_stale_pipeline_runs(older_than: timedelta) -> list[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            UPDATE pipeline_runs
            SET status = 'ERROR', updated_at = CURRENT_TIMESTAMP
            WHERE {RUN_NOT_TERMINAL}
            AND updated_at < NOW() - %s::interval
            RETURNING request_id::text
            """,
            (older_than,),
        )
        rows = await cur.fetchall()
    return [row[0] for row in rows]


async def get_pipeline_run_result(request_id: str):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT r.jurisdiction_ocdid FROM requests r
            JOIN pipeline_runs j ON j.request_id = r.id
            WHERE j.request_id = %s LIMIT 1
            """,
            (request_id,),
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return {"jurisdiction_ocdid": row[0]}
