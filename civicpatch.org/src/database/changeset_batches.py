"""Database queries for `changeset_batches` — one run that produced many requests.

A batch records the fan-out, not the outcome: `finished_at` means the requests exist, and what
happens to each afterwards is `requests`' business. Its items *are* its requests, so there is no
per-item store — what one did reads off `source_records` by `changeset_id`.
"""

import json
from enum import StrEnum

from database.database import get_pool
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


# How long a batch may hold the lock without finishing before the next caller takes it over.
# A real import is minutes: the whole sheet is read once and each locality is a handful of
# requests. This is the margin for a slow one, not a guess at a normal one.
STALE_AFTER = "2 hours"

ABANDONED = (
    "abandoned: nothing finished this batch, so the process it ran in died "
    "(a restart or a deploy). Released by the next import."
)


async def _release_abandoned(cur, lock_key: str) -> int:
    """Close any batch on this key that is old and still unfinished.

    `finish` runs in a `try/finally`-shaped path, so an *exception* already releases the lock.
    A process that dies does not run anything, and `changeset_batches_one_running_per_key` is
    `UNIQUE (lock_key) WHERE finished_at IS NULL` — so without this, one killed worker wedges
    every future import on that key permanently, repairable only by hand.

    Taken over here rather than swept on a timer: the only caller who cares is the next one, and
    it is about to prove the previous run is gone by starting.
    """
    await cur.execute(
        f"""
        UPDATE changeset_batches
           SET status = %s, error = COALESCE(error, %s), finished_at = now()
         WHERE lock_key = %s
           AND finished_at IS NULL
           AND started_at < now() - interval '{STALE_AFTER}'
        """,
        (BatchStatus.FAILED.value, ABANDONED, lock_key),
    )
    return cur.rowcount


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
        await _release_abandoned(cur, lock_key)
        try:
            await cur.execute(
                """
                INSERT INTO changeset_batches
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
            UPDATE changeset_batches
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
                   (SELECT count(*) FROM changesets WHERE changesets.batch_id = b.id) AS items_done,
                   b.error, b.started_by_user_id::text, b.started_at, b.finished_at
            FROM changeset_batches b WHERE b.id = %s
            """,
            (batch_id,),
        )
        row = await cur.fetchone()
        if row is None:
            return None
        columns = [column.name for column in cur.description or []]
    return dict(zip(columns, row))


async def list_recent(kind: BatchKind, limit: int = 25, offset: int = 0) -> list[dict]:
    """Recent batches of this kind, newest first.

    The history view and `latest` ask the same question at different depths, so they share a
    query rather than drifting over what "recent" means. `latest`'s `limit=1` never pages, so
    `offset` defaults to 0 rather than needing every caller to pass it.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT b.id::text, b.kind, b.lock_key, b.arguments_json, b.status,
                   b.items_total,
                   (SELECT count(*) FROM changesets WHERE changesets.batch_id = b.id) AS items_done,
                   b.error, b.started_by_user_id::text, b.started_at, b.finished_at
            FROM changeset_batches b
            WHERE b.kind = %s
            ORDER BY b.started_at DESC
            LIMIT %s OFFSET %s
            """,
            (kind.value, limit, offset),
        )
        rows = await cur.fetchall()
        columns = [column.name for column in cur.description or []]
    return [dict(zip(columns, row)) for row in rows]


async def count_by_kind(kind: BatchKind) -> int:
    """How many batches of this kind exist — the total a paged history reports against."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT count(*) FROM changeset_batches WHERE kind = %s", (kind.value,)
        )
        row = await cur.fetchone()
    assert row is not None
    return row[0]


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

    That is the whole reason `changesets.batch_id` exists rather than a stored result: between the
    import and somebody opening this page, a card may have been published or dismissed from the
    ordinary review queue, which an import-time snapshot would never know.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT changesets.id::text AS changeset_id, changesets.jurisdiction_ocdid,
                   changesets.changeset_state,
                   j.data->>'name' AS name
            FROM changesets
            LEFT JOIN jurisdictions j ON j.jurisdiction_ocdid = changesets.jurisdiction_ocdid
            WHERE changesets.batch_id = %s
            ORDER BY j.data->>'name', changesets.jurisdiction_ocdid
            """,
            (batch_id,),
        )
        columns = [column.name for column in cur.description or []]
        return [dict(zip(columns, row)) for row in await cur.fetchall()]
