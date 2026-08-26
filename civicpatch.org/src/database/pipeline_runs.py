from datetime import datetime, timedelta
from typing import Optional

from database.database import get_pool, to_iso
from psycopg import sql
from shared.utils.statuses import TERMINAL_PIPELINE_RUN_STATUSES


async def get_sourced_at(cur, request_id: str) -> datetime:
    """When the run last read the source.

    Stamped by the pipeline's own report, not at ingest, which can be hours later on a retry or
    a replayed artifact.
    """
    await cur.execute(
        "SELECT sourced_at FROM requests WHERE id::text = %s",
        (request_id,),
    )
    row = await cur.fetchone()
    if row is None:
        raise ValueError(f"No pipeline run for request {request_id}")
    return row[0]


async def get_pipeline_run(request_id: str):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT r.status, r.progress, r.arguments_json,
                   r.created_at, r.sourced_at, r.open_data_url
            FROM requests r
            WHERE r.id = %s;
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


async def get_active_pipeline_run_jurisdiction_ocdids() -> set[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT DISTINCT r.jurisdiction_ocdid
            FROM requests r
            WHERE r.status IS NOT NULL AND r.status != ALL(%s)
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
            FROM requests r
            WHERE r.status IS NOT NULL AND r.status != ALL(%s)
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
            SELECT r.id::text, r.status, r.progress, r.created_at, r.sourced_at,
                   r.jurisdiction_ocdid, jur.state, jur.data->>'name',
                   COUNT(*) OVER() AS total_count
            FROM requests r
            JOIN jurisdictions jur ON jur.jurisdiction_ocdid = r.jurisdiction_ocdid
            WHERE r.status IS NOT NULL AND r.status != ALL(%s)
            AND r.jurisdiction_ocdid IS NOT NULL
            AND r.request_type = 'people'
        """
        params: list = [list(TERMINAL_PIPELINE_RUN_STATUSES)]
        if state_code:
            query += " AND jur.state = %s"
            params.append(state_code.lower())
        query += " ORDER BY r.sourced_at DESC LIMIT %s OFFSET %s"
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


async def get_pipeline_run_status(request_id: str):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT status, progress FROM requests
            WHERE id = %s;
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

    # Every report re-stamps it: this is what dates `last_seen_at` on every membership.
    set_clauses.append("sourced_at = CURRENT_TIMESTAMP")

    if not set_clauses:
        return

    params.append(request_id)
    set_clause_str = ", ".join(set_clauses)

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            sql.SQL(f"""
            UPDATE requests
            SET {set_clause_str}
            WHERE id = %s;
            """),
            params,
        )


RUN_NOT_TERMINAL = (
    "requests.status IS NOT NULL AND requests.status != ALL(ARRAY["
    + ", ".join(f"'{status.value}'" for status in TERMINAL_PIPELINE_RUN_STATUSES)
    + "])"
)


async def expire_stale_pipeline_runs(older_than: timedelta) -> list[str]:
    """`sourced_at` is deliberately left alone: giving up on a run is not reading the source,
    and restamping it would make a stale request outrank a newer scrape in the sweep."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            UPDATE requests
            SET status = 'ERROR'
            WHERE {RUN_NOT_TERMINAL}
            AND sourced_at < NOW() - %s::interval
            RETURNING id::text
            """,
            (older_than,),
        )
        rows = await cur.fetchall()
    return [row[0] for row in rows]

