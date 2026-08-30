"""Database queries for `request_batches` — one run that produced many requests.

A batch records the fan-out, not the outcome: `finished_at` means the requests exist, and what
happens to each afterwards is `requests`' business. Its items *are* its requests, so there is no
per-item store — what one did reads off `source_records` by `request_id`.
"""

import json
from enum import StrEnum

from database.database import get_pool
from database.requests import REVIEW_STATUS
from psycopg.errors import UniqueViolation


class BatchKind(StrEnum):
    SHEET_IMPORT = "sheet_import"
    STATE_SCRAPE = "state_scrape"


class BatchStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class BatchAlreadyRunning(Exception):
    """Raised, not returned: a second run over one target is not a state the caller can carry
    on from."""

    def __init__(self, lock_key: str):
        super().__init__(f"a batch is already running for {lock_key}")
        self.lock_key = lock_key


async def start(
    kind: BatchKind,
    lock_key: str,
    started_by_user_id: str,
    arguments_json: dict,
    items_total: int | None = None,
) -> str:
    """Claim the lock and open a batch. The claim *is* the insert, so there is no
    check-then-act window for two callers to race through."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        try:
            await cur.execute(
                """
                INSERT INTO request_batches
                    (kind, lock_key, arguments_json, started_by_user_id, items_total)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id::text
                """,
                (
                    kind.value,
                    lock_key,
                    json.dumps(arguments_json),
                    started_by_user_id,
                    items_total,
                ),
            )
        except UniqueViolation as e:
            raise BatchAlreadyRunning(lock_key) from e
        row = await cur.fetchone()
        assert row is not None
    return row[0]


async def finish(batch_id: str, status: BatchStatus, error: str | None = None) -> None:
    """Close the batch. `finished_at` is what the lock keys on, so this must happen even when
    the batch failed."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE request_batches
               SET status = %s, error = %s, finished_at = now()
             WHERE id = %s
            """,
            (status.value, error, batch_id),
        )


async def get(batch_id: str) -> dict | None:
    """One batch, for the progress poll. `items_done` is counted rather than stored."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT b.id::text, b.kind, b.lock_key, b.arguments_json, b.status,
                   b.items_total,
                   (SELECT count(*) FROM requests WHERE requests.batch_id = b.id) AS items_done,
                   b.error, b.started_by_user_id::text, b.started_at, b.finished_at
            FROM request_batches b WHERE b.id = %s
            """,
            (batch_id,),
        )
        row = await cur.fetchone()
        if row is None:
            return None
        columns = [column.name for column in cur.description or []]
    return dict(zip(columns, row))


async def list_recent(kind: BatchKind, limit: int = 25) -> list[dict]:
    """Recent batches of this kind, newest first.

    The history view and `latest` ask the same question at different depths, so they share a
    query rather than drifting over what "recent" means.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT b.id::text, b.kind, b.lock_key, b.arguments_json, b.status,
                   b.items_total,
                   (SELECT count(*) FROM requests WHERE requests.batch_id = b.id) AS items_done,
                   b.error, b.started_by_user_id::text, b.started_at, b.finished_at
            FROM request_batches b
            WHERE b.kind = %s
            ORDER BY b.started_at DESC
            LIMIT %s
            """,
            (kind.value, limit),
        )
        rows = await cur.fetchall()
        columns = [column.name for column in cur.description or []]
    return [dict(zip(columns, row)) for row in rows]


async def latest(kind: BatchKind) -> dict | None:
    """The most recent batch of this kind, so a page load can find one already under way.

    Server-side rather than remembered by whoever started it: one spreadsheet means one import,
    and a second maintainer opening the page should see the run in progress rather than a
    Start button that will 409.
    """
    recent = await list_recent(kind, limit=1)
    return recent[0] if recent else None


async def items(batch_id: str) -> list[dict]:
    """The batch's requests with their *current* review state, not the state they were made in.

    That is the whole reason `requests.batch_id` exists rather than a stored result: between the
    import and somebody opening this page, a card may have been published or dismissed from the
    ordinary review queue, which an import-time snapshot would never know.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT r.id::text AS request_id, r.jurisdiction_ocdid,
                   {REVIEW_STATUS} AS review_status,
                   j.data->>'name' AS name
            FROM requests r
            LEFT JOIN jurisdictions j ON j.jurisdiction_ocdid = r.jurisdiction_ocdid
            WHERE r.batch_id = %s
            ORDER BY j.data->>'name', r.jurisdiction_ocdid
            """,
            (batch_id,),
        )
        columns = [column.name for column in cur.description or []]
        return [dict(zip(columns, row)) for row in await cur.fetchall()]
