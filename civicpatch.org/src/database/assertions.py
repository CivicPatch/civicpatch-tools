"""Database queries for `assertions` — the field values a human has accepted or rejected.

Current state, not a log: setting a value again overwrites, withdrawing deletes. `change_logs`
is the history.

Two entry points: `upsert` on a caller's cursor, `create` owning its own connection — a label
edit and the assertion protecting it must commit together.
"""

import json

from core.people_edits import LIST_FIELDS
from database.database import get_pool
from schemas.assertions import Assertion, AssertionKind, EntityType

# Must match the two partial indexes in 137 exactly; a mismatch is an unhandled unique violation.
_REPLACES_THE_FIELD = """(entity_type, entity_id, field_path)
    WHERE kind = 'accept'
      AND field_path NOT IN ('other_names', 'phones', 'emails', 'urls', 'source_urls')"""

_REPLACES_THE_VALUE = """(entity_type, entity_id, field_path, value)
    WHERE kind = 'reject'
       OR field_path IN ('other_names', 'phones', 'emails', 'urls', 'source_urls')"""


def _keyed_by_value(assertion: Assertion) -> bool:
    """Only a scalar accept replaces the field's one answer; list fields and rejects key on the
    value."""
    return assertion.kind is AssertionKind.REJECT or assertion.field_path in LIST_FIELDS


_DROP_THE_OPPOSITE = """
    DELETE FROM assertions
    WHERE entity_type = %s AND entity_id = %s AND field_path = %s
      AND kind <> %s AND value = %s
"""


async def upsert(cur, assertion: Assertion, asserted_by: str) -> str:
    """Record one claim on a caller's cursor. Returns its id.

    Re-stating an existing claim refreshes who and when rather than adding a row, which bounds
    this table by distinct values instead of by publish count.
    """
    entity = (assertion.entity_type.value, assertion.entity_id, assertion.field_path)
    value = json.dumps(assertion.value)
    conflict = (
        _REPLACES_THE_VALUE if _keyed_by_value(assertion) else _REPLACES_THE_FIELD
    )

    await cur.execute(_DROP_THE_OPPOSITE, (*entity, assertion.kind.value, value))
    await cur.execute(
        f"""
        INSERT INTO assertions
            (entity_type, entity_id, field_path, kind, value, sources, asserted_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT {conflict}
        DO UPDATE SET value = EXCLUDED.value,
                      sources = EXCLUDED.sources,
                      asserted_by = EXCLUDED.asserted_by,
                      asserted_at = now()
        RETURNING id::text
        """,
        (*entity, assertion.kind.value, value, _sources(assertion), asserted_by),
    )
    row = await cur.fetchone()
    return row[0] if row else ""


def _sources(assertion: Assertion) -> str | None:
    if not assertion.sources:
        return None
    return json.dumps([source.model_dump() for source in assertion.sources])


async def withdraw(
    cur, entity_type: EntityType, entity_id: str, field_path: str
) -> int:
    """Stop accepting a field. Returns how many rows went.

    A delete: `value` is NOT NULL, so a withdrawal has no value to carry.
    """
    await cur.execute(
        """
        DELETE FROM assertions
        WHERE entity_type = %s AND entity_id = %s AND field_path = %s AND kind = 'accept'
        """,
        (entity_type.value, entity_id, field_path),
    )
    return cur.rowcount


async def create(assertion: Assertion, asserted_by: str) -> str:
    """Set one assertion, owning the connection. Returns its id.

    `asserted_by` is required: an assertion nobody made is not an assertion.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        assertion_id = await upsert(cur, assertion, asserted_by)
        await conn.commit()
    return assertion_id


async def create_all(claims: list[Assertion], asserted_by: str) -> None:
    """Record a whole save's worth of claims, owning the connection.

    One transaction: half a reviewer's answer is worse than none, because the half that landed
    looks like a decision they made.
    """
    if not claims:
        return
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        for claim in claims:
            await upsert(cur, claim, asserted_by)
        await conn.commit()


async def list_for_entities(
    cur, entity_type: EntityType, entity_ids: list[str]
) -> dict[str, list[dict]]:
    """Every assertion about these rows, newest first, keyed by entity id.

    Carries who and when, which `stated_values` does not — the editor tags each field with the
    person behind it.
    """
    if not entity_ids:
        return {}
    await cur.execute(
        """
        SELECT a.entity_id::text, a.id::text, a.field_path, a.kind, a.value, a.sources,
               a.asserted_at, a.asserted_by::text,
               COALESCE(u.display_name, u.email) AS asserted_by_name
        FROM assertions a
        LEFT JOIN users u ON u.id = a.asserted_by
        WHERE a.entity_type = %s AND a.entity_id::text = ANY(%s)
        ORDER BY a.asserted_at DESC
        """,
        (entity_type.value, entity_ids),
    )
    columns = [column.name for column in cur.description or []][1:]
    by_entity: dict[str, list[dict]] = {}
    for row in await cur.fetchall():
        by_entity.setdefault(row[0], []).append(dict(zip(columns, row[1:])))
    return by_entity


async def stated_values(
    cur, entity_type: EntityType, entity_ids: list[str]
) -> dict[str, dict]:
    """`{entity_id: {field: {"accept": [...], "reject": [...]}}}` for these rows.

    Both kinds together, because applying them is `(scraped ∪ accepted) − rejected`. A row
    nobody has judged is absent rather than empty.
    """
    if not entity_ids:
        return {}
    await cur.execute(
        """
        SELECT entity_id::text, field_path, kind, value
        FROM assertions
        WHERE entity_type = %s AND entity_id::text = ANY(%s)
        """,
        (entity_type.value, entity_ids),
    )
    stated: dict[str, dict] = {}
    for entity_id, field_path, kind, value in await cur.fetchall():
        by_kind = stated.setdefault(entity_id, {}).setdefault(
            field_path, {AssertionKind.ACCEPT: [], AssertionKind.REJECT: []}
        )
        by_kind[kind].append(value)
    return stated
