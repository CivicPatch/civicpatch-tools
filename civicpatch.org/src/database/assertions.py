"""Database queries for `assertions` — what a human said about a row.

APPEND-ONLY. There is no update and no delete here, and that is the point: verification needs
history, and history is only trustworthy if rows never change. A mistake is retracted by a
later row, not by editing the first.

Current state is therefore derived, never stored — the latest row per (entity, field).

Distinct from `change_logs`, which records *what happened*. An audit log says someone edited a
field; it cannot say someone checked a field and found it already correct.

Two entry points: `insert` on a caller's cursor, `create` owning its own connection. The pair
exists because a membership label and the assertion protecting it must commit together.
"""

import json

from database.database import get_pool
from schemas.assertions import Assertion, AssertionKind, EntityType


async def insert(cur, assertion: Assertion, asserted_by: str) -> str:
    """Append one assertion on a caller's cursor. Returns its id.

    The cursor variant exists because a human's label edit and the assertion protecting it from
    the next scrape are one act — landing them in separate transactions would leave a window
    where the label is set and unprotected.
    """
    await cur.execute(
        """
        INSERT INTO assertions
            (entity_type, entity_id, field_path, kind, value, sources, asserted_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id::text
        """,
        (
            assertion.entity_type.value,
            assertion.entity_id,
            assertion.field_path,
            assertion.kind.value,
            json.dumps(assertion.value) if assertion.value is not None else None,
            json.dumps([source.model_dump() for source in assertion.sources])
            if assertion.sources
            else None,
            asserted_by,
        ),
    )
    row = await cur.fetchone()
    return row[0] if row else ""


async def create(assertion: Assertion, asserted_by: str) -> str:
    """Append one assertion. Returns its id.

    `create`, not `upsert` — `memberships.upsert` opens a row or advances one, while this only
    ever inserts. Named for the write it performs, per the persistence verbs.

    `asserted_by` is required, unlike `requests.resolved_by_user_id` where NULL means a machine
    gave up. An assertion nobody made is not an assertion.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        assertion_id = await insert(cur, assertion, asserted_by)
        await conn.commit()
    return assertion_id


async def list_for_entity(cur, entity_type: EntityType, entity_id: str) -> list[dict]:
    """Every assertion about one row, newest first. The reason this is a table."""
    await cur.execute(
        """
        SELECT a.id::text, a.field_path, a.kind, a.value, a.sources,
               a.asserted_at, a.asserted_by::text,
               COALESCE(u.display_name, u.email) AS asserted_by_name
        FROM assertions a
        LEFT JOIN users u ON u.id = a.asserted_by
        WHERE a.entity_type = %s AND a.entity_id = %s
        ORDER BY a.asserted_at DESC
        """,
        (entity_type.value, entity_id),
    )
    columns = [column.name for column in cur.description or []]
    return [dict(zip(columns, row)) for row in await cur.fetchall()]


async def current_corrections(cur, entity_type: EntityType, entity_id: str) -> dict:
    """The value a human last asserted for each field — what the publish merge applies.

    `DISTINCT ON` rather than a stored current-value row: the log is the truth, and deriving
    the latest is what lets a correction be superseded or retracted without losing that it was
    ever made.

    A field whose latest assertion is a retraction has no current correction, which is what
    makes retraction work at all.
    """
    await cur.execute(
        """
        SELECT DISTINCT ON (field_path) field_path, kind, value
        FROM assertions
        WHERE entity_type = %s AND entity_id = %s AND field_path IS NOT NULL
        ORDER BY field_path, asserted_at DESC
        """,
        (entity_type.value, entity_id),
    )
    return {
        row[0]: row[2] for row in await cur.fetchall() if row[1] == AssertionKind.CORRECT
    }
