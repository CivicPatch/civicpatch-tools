"""Database queries for `assertions` — the field values a human currently stands behind.

CURRENT STATE, not a log. Setting a value again overwrites; withdrawing one deletes. It was
append-only until 137, and that could not express *un-rejecting*: accepting a value you had
rejected forces it to **be** the value, where unblocking merely lets the scraper decide again.
Saying that needed a third kind and latest-wins ordering in every reader — and readers forget,
which is how `POST_IS_VERIFIED` came to treat a retracted confirmation as still confirming.

Nothing is lost by that. `change_logs` already records every editable field on both edit paths,
and assertions are written from edits, so the history is there by construction.

  change_logs  — what happened. Append-only, audit.
  assertions   — what is claimed now. Mutable, small, one row per live claim.

Two entry points: `insert` on a caller's cursor, `create` owning its own connection. The pair
exists because a membership label and the assertion protecting it must commit together.
"""

import json

from database.database import get_pool
from schemas.assertions import Assertion, AssertionKind, EntityType

# The editable fields that hold several values. A list field is a set — `(scraped ∪ accepted) −
# rejected`, both kinds naming one element — so it can carry many accepts. A scalar has one
# answer and carries one. Mirrors the two partial unique indexes in 137.
LIST_FIELDS = frozenset({"other_names", "phones", "emails", "urls", "source_urls"})


# Which uniqueness rule the row lives under, and therefore what re-stating it means. A scalar
# accept replaces the one answer; anything keyed by value refreshes that value's row. Same
# spelling as the two partial indexes in 137 — a mismatch here is an unhandled unique violation.
_REPLACES_THE_FIELD = """(entity_type, entity_id, field_path)
    WHERE kind = 'accept'
      AND field_path NOT IN ('other_names', 'phones', 'emails', 'urls', 'source_urls')"""

_REPLACES_THE_VALUE = """(entity_type, entity_id, field_path, value)
    WHERE kind = 'reject'
       OR field_path IN ('other_names', 'phones', 'emails', 'urls', 'source_urls')"""


async def insert(cur, assertion: Assertion, asserted_by: str) -> str:
    """State one assertion on a caller's cursor. Returns its id.

    Re-stating what is already claimed is not a second row — it refreshes who stood behind it
    and when. That is what keeps this table bounded by *distinct values* rather than by publish
    count: republishing an unchanged roster every week adds nothing after the first pass.

    The cursor variant exists because a human's label edit and the assertion protecting it from
    the next scrape are one act — landing them in separate transactions would leave a window
    where the label is set and unprotected.
    """
    scalar_accept = (
        assertion.kind is AssertionKind.ACCEPT
        and assertion.field_path not in LIST_FIELDS
    )
    conflict = _REPLACES_THE_FIELD if scalar_accept else _REPLACES_THE_VALUE
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
        (
            assertion.entity_type.value,
            assertion.entity_id,
            assertion.field_path,
            assertion.kind.value,
            json.dumps(assertion.value),
            json.dumps([source.model_dump() for source in assertion.sources])
            if assertion.sources
            else None,
            asserted_by,
        ),
    )
    row = await cur.fetchone()
    return row[0] if row else ""


async def withdraw(cur, entity_type: EntityType, entity_id: str, field_path: str) -> int:
    """Stop standing behind a field. Returns how many rows went.

    A delete, because there is nothing to say instead: `value` is NOT NULL, so "I withdraw" has
    no value to carry. Under the old append-only model this needed a third kind whose only job
    was to cancel a row that could not be removed.
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


async def stated_values(cur, entity_type: EntityType, entity_id: str) -> dict[str, dict]:
    """What a human currently stands behind for this row, as `{field: {"accept": [...],
    "reject": [...]}}`.

    Both sides in one read: publishing a field needs the accepts and the rejects together —
    `(scraped ∪ accepted) − rejected` — and fetching them separately would let one arrive
    without the other.

    Lists, not single values, because a list field carries one row per element. A scalar field
    has exactly one accept, enforced by index rather than by whoever reads this remembering to
    take the latest.
    """
    await cur.execute(
        """
        SELECT field_path, kind, value
        FROM assertions
        WHERE entity_type = %s AND entity_id = %s
        """,
        (entity_type.value, entity_id),
    )
    stated: dict[str, dict] = {}
    for field_path, kind, value in await cur.fetchall():
        by_kind = stated.setdefault(field_path, {AssertionKind.ACCEPT: [], AssertionKind.REJECT: []})
        by_kind[kind].append(value)
    return stated
