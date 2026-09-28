"""Database queries for `claims` — the field values a human has accepted or rejected.

Append-only: setting a value again inserts, withdrawing files a withdraw row naming it, and `created_by`/`created_at` are never rewritten — `claimed_values` resolves what applies now
by reading, not by holding one row per field."""

import json
from typing import Any

from core.people_edits import LIST_FIELDS, POSTS_FIELD
from database.database import get_pool
from schemas.claims import Claim, ClaimKind, DefaultNote, EntityType, Source

# Fields whose accepts are per value rather than one answer for the whole field: the list
# fields, and the posts somebody holds — two organizations, two claims, neither superseding
# the other.
_MULTI_VALUED = LIST_FIELDS | {POSTS_FIELD}


def _value_keyed(field_path: str, kind: str) -> bool:
    """Only a scalar accept has one answer for the whole field; a reject (of either field
    shape) and a multi-valued field's accept are per-value, so distinct values coexist."""
    return kind == ClaimKind.REJECT.value or field_path in _MULTI_VALUED


# "Whichever value currently wins", for a caller that does not mean one in particular. `None`
# cannot say it: a claim's value may itself be null.
_WHOLE_FIELD = object()


def _keyed_by_value(claim: Claim) -> bool:
    return _value_keyed(claim.field_path, claim.kind.value)


_INSERT = """
    INSERT INTO claims
        (entity_type, entity_id, field_path, kind, value, sources, created_by, changeset_id,
         created_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, clock_timestamp())
"""
# clock_timestamp(), not the column's own `now()` default: `now()` is transaction_timestamp(),
# frozen for every statement in one transaction. A single save's `executemany` batch (many
# claims, one transaction) would then insert them all with the SAME created_at, and `id` is
# gen_random_uuid() — not time-ordered — so "most recent claim per value" would tie-break at
# random between claims from the same save. clock_timestamp() is the real wall clock, distinct
# per statement, which is what makes "latest wins" mean anything within a batch.

# The one ordering "latest wins" means anywhere in this file — claimed_values, the lookup
# below, and withdraw's own target all have to rank ties the same way, or they could disagree
# about which row is current. One constant, so they can't drift apart from each other.
LATEST_FIRST = "ORDER BY created_at DESC, id DESC"


def _conflict_key(claim: Claim) -> tuple:
    """Which earlier claim IN THIS SAME BATCH a claim would restate, if any — a save must not
    ask to insert two rows that would immediately contradict each other."""
    field = (claim.entity_type.value, claim.entity_id, claim.field_path)
    return (*field, json.dumps(claim.value)) if _keyed_by_value(claim) else field


def latest_of_each(claims: list[Claim]) -> list[Claim]:
    return list({_conflict_key(claim): claim for claim in claims}.values())


async def _unchanged(cur, claims: list[Claim]) -> set[tuple]:
    """The `_conflict_key`s already the current winner per `claimed_values` — restating an
    old, since-superseded value is a real new claim, not a no-op."""
    by_entity: dict[str, set[str]] = {}
    for claim in claims:
        by_entity.setdefault(claim.entity_type.value, set()).add(claim.entity_id)

    current: dict[str, dict] = {}
    for entity_type_value, entity_ids in by_entity.items():
        current.update(
            await claimed_values(
                cur, EntityType(entity_type_value), sorted(entity_ids)
            )
        )

    def already_true(claim: Claim) -> bool:
        by_field = current.get(claim.entity_id, {}).get(claim.field_path, {})
        return claim.value in (by_field.get(claim.kind) or [])

    return {_conflict_key(claim) for claim in claims if already_true(claim)}


async def upsert_all(cur, claims: list[Claim], created_by: str) -> None:
    """Append a save's worth of claims. Never overwrites: a claim already the current winner
    is skipped so an unrelated save does not churn a new row for every field
    `claims_from_edit` walks past unchanged."""
    claims = latest_of_each(claims)
    if not claims:
        return

    unchanged = await _unchanged(cur, claims)
    claims = [c for c in claims if _conflict_key(c) not in unchanged]
    if not claims:
        return

    await cur.executemany(
        _INSERT,
        [
            (
                claim.entity_type.value,
                claim.entity_id,
                claim.field_path,
                claim.kind.value,
                json.dumps(claim.value),
                _sources(claim),
                created_by,
                claim.changeset_id,
            )
            for claim in claims
        ],
    )


_CURRENT_ROW_FOR = f"""
    SELECT id::text FROM claims
    WHERE entity_type = %s AND entity_id = %s AND field_path = %s
      AND kind = %s AND value = %s AND claim_is_live(id)
    {LATEST_FIRST}
    LIMIT 1
"""


async def upsert(cur, claim: Claim, created_by: str) -> str:
    """Record one claim on a caller's cursor. Returns its id — the new row's, or the existing
    row's if this only restates the current winner (see `upsert_all`)."""
    entity = (claim.entity_type.value, claim.entity_id, claim.field_path)
    value = json.dumps(claim.value)

    if await _unchanged(cur, [claim]):
        await cur.execute(_CURRENT_ROW_FOR, (*entity, claim.kind.value, value))
        row = await cur.fetchone()
        return row[0] if row else ""

    await cur.execute(
        f"{_INSERT} RETURNING id::text",
        (
            *entity,
            claim.kind.value,
            value,
            _sources(claim),
            created_by,
            claim.changeset_id,
        ),
    )
    row = await cur.fetchone()
    return row[0] if row else ""


def _sources(claim: Claim) -> str:
    return json.dumps([source.model_dump() for source in claim.sources])


# Idempotent per target, so a rerun files no second withdraw for a fact that is already dead.
_INSERT_WITHDRAW = """
    INSERT INTO claims
        (entity_type, entity_id, field_path, kind, value, sources, created_by, changeset_id)
    SELECT %(entity_type)s, %(entity_id)s::uuid, NULL, %(kind)s, 'null'::jsonb,
           %(sources)s::jsonb, %(created_by)s, %(changeset_id)s
    WHERE NOT EXISTS (
        SELECT 1 FROM claims
         WHERE kind = %(kind)s AND entity_type = %(entity_type)s
           AND entity_id = %(entity_id)s::uuid AND claim_is_live(id)
    )
"""


async def withdraw_facts(
    cur,
    entity_type: EntityType,
    entity_ids: list[str],
    withdrawn_by: str,
    changeset_id: str,
    reason: str | None = None,
) -> None:
    """File a withdraw against each of these facts: claims, source records or source pages.

    A withdraw names a whole row rather than a value, which is why it carries no field and no
    value. Withdrawing one is itself a fact, so undoing a withdrawal is withdrawing it.
    """
    if not entity_ids:
        return
    sources = json.dumps([Source(note=reason or DefaultNote.WITHDRAWN).model_dump()])
    await cur.executemany(
        _INSERT_WITHDRAW,
        [
            {
                "entity_type": entity_type.value,
                "entity_id": entity_id,
                "kind": ClaimKind.WITHDRAW.value,
                "sources": sources,
                "created_by": withdrawn_by,
                "changeset_id": changeset_id,
            }
            for entity_id in entity_ids
        ],
    )


async def create(claim: Claim, created_by: str) -> str:
    """Set one claim, owning the connection. Returns its id.

    `created_by` is required: an claim nobody made is not an claim.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        claim_id = await upsert(cur, claim, created_by)
        await conn.commit()
    return claim_id


async def create_all(claims: list[Claim], created_by: str) -> None:
    """Record a whole save's worth of claims, owning the connection.

    One transaction: half a reviewer's answer is worse than none, because the half that landed
    looks like a decision they made.
    """
    if not claims:
        return
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await upsert_all(cur, claims, created_by)
        await conn.commit()


async def list_for_entities(
    cur, entity_type: EntityType, entity_ids: list[str]
) -> dict[str, list[dict]]:
    """Every claim about these rows, newest first, keyed by entity id.

    Carries who and when, which `claimed_values` does not — the editor tags each field with the
    person behind it.
    """
    if not entity_ids:
        return {}
    await cur.execute(
        """
        SELECT a.entity_id::text, a.id::text, a.field_path, a.kind, a.value, a.sources,
               a.created_at, a.created_by::text,
               COALESCE(u.username, u.email) AS created_by_name
        FROM claims a
        LEFT JOIN users u ON u.id = a.created_by
        WHERE a.entity_type = %s AND a.entity_id::text = ANY(%s)
        ORDER BY a.created_at DESC
        """,
        (entity_type.value, entity_ids),
    )
    columns = [column.name for column in cur.description or []][1:]
    by_entity: dict[str, list[dict]] = {}
    for row in await cur.fetchall():
        by_entity.setdefault(row[0], []).append(dict(zip(columns, row[1:])))
    return by_entity


async def claimed_values(
    cur, entity_type: EntityType, entity_ids: list[str]
) -> dict[str, dict]:
    """`{entity_id: {field: {"accept": [...], "reject": [...]}}}` — only the claim that
    currently applies (`(scraped ∪ accepted) − rejected`), never a withdrawn or superseded one.
    A scalar field has one current answer; a list field's accept/reject are per-value, so each
    value's own most recent claim wins independently — never both sides at once."""
    if not entity_ids:
        return {}
    await cur.execute(
        f"""
        SELECT entity_id::text, field_path, kind, value
        FROM claims
        WHERE entity_type = %s AND entity_id::text = ANY(%s) AND claim_is_live(id)
        {LATEST_FIRST}
        """,
        (entity_type.value, entity_ids),
    )
    claimed: dict[str, dict] = {}
    seen: set[tuple] = set()
    for entity_id, field_path, kind, value in await cur.fetchall():
        # Rows arrive newest first, so the first time a key is seen is its current winner —
        # everything after is history a newer claim has already superseded.
        key = (
            # By the value's JSON text: a membership claim's value is the post's key, an object.
            (entity_id, field_path, json.dumps(value, sort_keys=True))
            if _value_keyed(field_path, kind)
            else (entity_id, field_path)
        )
        if key in seen:
            continue
        seen.add(key)
        by_kind = claimed.setdefault(entity_id, {}).setdefault(
            field_path, {ClaimKind.ACCEPT: [], ClaimKind.REJECT: []}
        )
        by_kind[kind].append(value)
    return claimed
