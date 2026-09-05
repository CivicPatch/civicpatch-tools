import json
from datetime import timedelta
from typing import Optional

import database.changesets as changesets_db
from database.database import get_pool, to_iso
from psycopg import sql
from shared.utils.statuses import (
    DismissalReason,
    PipelineRunStatus,
    TERMINAL_PIPELINE_RUN_STATUSES,
)

_TERMINAL = TERMINAL_PIPELINE_RUN_STATUSES


async def register_run(
    run_id: str,
    jurisdiction_ocdid: str,
    arguments_json: dict,
    created_by_user_id: Optional[str] = None,
    status: PipelineRunStatus = PipelineRunStatus.PENDING,
    progress: int = 0,
    if_not_exists: bool = False,
) -> None:
    """Start an attempt. No changeset — one is minted at ingest, and only if the run succeeds."""
    pool = await get_pool()
    conflict = "ON CONFLICT (id) DO NOTHING" if if_not_exists else ""
    async with pool.connection() as conn:
        await conn.execute(
            sql.SQL(f"""
            INSERT INTO pipeline_runs (
                id, jurisdiction_ocdid, arguments_json, created_by_user_id, status, progress
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            {conflict}
            """),
            (
                run_id,
                jurisdiction_ocdid,
                json.dumps(arguments_json),
                created_by_user_id,
                status,
                progress,
            ),
        )


async def get_pipeline_run(run_id: str):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        # `change_url` belongs to the proposal, not the attempt, so it is joined rather than
        # copied — a run that proposed nothing has none.
        await cur.execute(
            """
            SELECT r.status, r.progress, r.arguments_json,
                   r.created_at, r.updated_at, c.change_url, r.changeset_id::text
            FROM pipeline_runs r
            LEFT JOIN changesets c ON c.id = r.changeset_id
            WHERE r.id = %s;
            """,
            (run_id,),
        )
        row = await cur.fetchone()
        if row:
            return {
                # The changeset this run minted, or None if it never reached ingest. It used to
                # echo `run_id` back, from before the two had separate ids.
                "changeset_id": row[6],
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
            "SELECT DISTINCT jurisdiction_ocdid FROM pipeline_runs WHERE finished_at IS NULL"
        )
        return {row[0] for row in await cur.fetchall()}


async def get_active_pipeline_run_jurisdiction_ocdids_by_state(
    state_code: str,
) -> set[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT DISTINCT jurisdiction_ocdid
            FROM pipeline_runs
            WHERE finished_at IS NULL AND jurisdiction_ocdid LIKE %s
            """,
            (f"%state:{state_code}%",),
        )
        return {row[0] for row in await cur.fetchall()}


async def get_active_pipeline_runs(
    state_code: Optional[str] = None, page: int = 1, per_page: int = 25
) -> tuple[list[dict], int]:
    pool = await get_pool()
    offset = (page - 1) * per_page
    async with pool.connection() as conn, conn.cursor() as cur:
        query = """
            SELECT r.id::text, r.status, r.progress, r.created_at, r.updated_at,
                   r.jurisdiction_ocdid, jur.state, jur.data->>'name',
                   COUNT(*) OVER() AS total_count
            FROM pipeline_runs r
            JOIN jurisdictions jur ON jur.jurisdiction_ocdid = r.jurisdiction_ocdid
            WHERE r.finished_at IS NULL
        """
        params: list = []
        if state_code:
            query += " AND jur.state = %s"
            params.append(state_code.lower())
        query += " ORDER BY r.updated_at DESC LIMIT %s OFFSET %s"
        params.extend([per_page, offset])
        await cur.execute(query, params)
        rows = await cur.fetchall()
        total = rows[0][8] if rows else 0
        return [
            {
                "changeset_id": row[0],
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


async def get_pipeline_run_status(run_id: str):
    """Where the run is, and whether it has been stopped.

    The pipeline engine polls this every loop and checks one thing: `== CANCELLED`. So the
    cancellation half is answered from the changeset's `dismissed_at`, which is durable and set
    in the same transaction as the dismissal — rather than from `status`, which is a live signal
    a cache could lose.

    A cancelled run is reported as cancelled whatever its last report said, which is the point:
    the pipeline stopped mattering the moment somebody stopped it.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT CASE WHEN c.dismissed_reason = %s
                        THEN '{PipelineRunStatus.CANCELLED.value}'
                        ELSE r.status END,
                   r.progress
            FROM pipeline_runs r
            LEFT JOIN changesets c ON c.id = r.changeset_id
            WHERE r.id = %s;
            """,
            (DismissalReason.CANCELLED, run_id),
        )
        row = await cur.fetchone()
        if row:
            return {"changeset_id": run_id, "status": row[0], "progress": row[1]}
        return None


async def update_pipeline_run_status(
    run_id: str, status: str | None = None, progress: Optional[int] = None
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
        # A terminal report is what ends the run, and `finished_at` is what every reader asks
        # about instead of matching the status against a list of terminal names.
        set_clauses.append(
            "finished_at = CASE WHEN %s = ANY(%s) THEN CURRENT_TIMESTAMP ELSE finished_at END"
        )
        params.extend([status, [s.value for s in _TERMINAL]])

    # Every report re-stamps it: this is what dates `last_seen_at` on every membership.
    set_clauses.append("updated_at = CURRENT_TIMESTAMP")

    if not set_clauses:
        return

    params.append(run_id)
    set_clause_str = ", ".join(set_clauses)

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            sql.SQL(f"""
            UPDATE pipeline_runs
            SET {set_clause_str}
            WHERE id = %s;
            """),
            params,
        )


async def expire_stale_pipeline_runs(older_than: timedelta) -> list[str]:
    """Settle runs that stopped reporting. A dead run sends no failure — it just goes quiet.

    Two steps, because that is the lifecycle: the silence is an `errored` event moving the run
    from `running` to `failed`, and the dismissal of whatever it proposed follows from there.
    Both in one transaction, so a run cannot be marked failed and left undismissed.

    `updated_at` is deliberately left alone: giving up on a run is not reading the source, and
    restamping it would make a stale request outrank a newer scrape in the sweep.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE pipeline_runs
            SET status = 'ERROR', finished_at = CURRENT_TIMESTAMP
            WHERE finished_at IS NULL
            AND updated_at < NOW() - %s::interval
            RETURNING COALESCE(changeset_id::text, id::text)
            """,
            (older_than,),
        )
        expired = [row[0] for row in await cur.fetchall()]
        await changesets_db.mark_dismissed(cur, expired, DismissalReason.ERRORED)
        await conn.commit()
    return expired
