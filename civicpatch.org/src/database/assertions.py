"""Database queries for `assertions` — the field values a human has accepted or rejected.

Append-only: setting a value again inserts, withdrawing stamps a row rather than deleting it,
and `created_by`/`created_at` are never rewritten — `asserted_values` resolves what applies now
by reading, not by holding one row per field."""

import json

from core.people_edits import LIST_FIELDS
from database.database import get_pool
from schemas.assertions import Assertion, AssertionKind, EntityType


def _value_keyed(field_path: str, kind: str) -> bool:
    """Only a scalar accept has one answer for the whole field; a reject (of either field
    shape) and a list field's accept are per-value, so distinct values coexist."""
    return kind == AssertionKind.REJECT.value or field_path in LIST_FIELDS


def _keyed_by_value(assertion: Assertion) -> bool:
    return _value_keyed(assertion.field_path, assertion.kind.value)


_INSERT = """
    INSERT INTO assertions
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

# The one ordering "latest wins" means anywhere in this file — asserted_values, the lookup
# below, and withdraw's own target all have to rank ties the same way, or they could disagree
# about which row is current. One constant, so they can't drift apart from each other.
LATEST_FIRST = "ORDER BY created_at DESC, id DESC"


def _conflict_key(claim: Assertion) -> tuple:
    """Which earlier claim IN THIS SAME BATCH a claim would restate, if any — a save must not
    ask to insert two rows that would immediately contradict each other."""
    field = (claim.entity_type.value, claim.entity_id, claim.field_path)
    return (*field, json.dumps(claim.value)) if _keyed_by_value(claim) else field


def latest_of_each(claims: list[Assertion]) -> list[Assertion]:
    return list({_conflict_key(claim): claim for claim in claims}.values())


async def _unchanged(cur, claims: list[Assertion]) -> set[tuple]:
    """The `_conflict_key`s already the current winner per `asserted_values` — restating an
    old, since-superseded value is a real new claim, not a no-op."""
    by_entity: dict[str, set[str]] = {}
    for claim in claims:
        by_entity.setdefault(claim.entity_type.value, set()).add(claim.entity_id)

    current: dict[str, dict] = {}
    for entity_type_value, entity_ids in by_entity.items():
        current.update(
            await asserted_values(cur, EntityType(entity_type_value), sorted(entity_ids))
        )

    def already_true(claim: Assertion) -> bool:
        by_field = current.get(claim.entity_id, {}).get(claim.field_path, {})
        return claim.value in (by_field.get(claim.kind) or [])

    return {_conflict_key(claim) for claim in claims if already_true(claim)}


async def upsert_all(cur, claims: list[Assertion], created_by: str) -> None:
    """Append a save's worth of claims. Never overwrites: a claim already the current winner
    is skipped so an unrelated save does not churn a new row for every field
    `assertions_from_edit` walks past unchanged."""
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
    SELECT id::text FROM assertions
    WHERE entity_type = %s AND entity_id = %s AND field_path = %s
      AND kind = %s AND value = %s AND withdrawn_at IS NULL
    {LATEST_FIRST}
    LIMIT 1
"""


async def upsert(cur, assertion: Assertion, created_by: str) -> str:
    """Record one claim on a caller's cursor. Returns its id — the new row's, or the existing
    row's if this only restates the current winner (see `upsert_all`)."""
    entity = (assertion.entity_type.value, assertion.entity_id, assertion.field_path)
    value = json.dumps(assertion.value)

    if await _unchanged(cur, [assertion]):
        await cur.execute(_CURRENT_ROW_FOR, (*entity, assertion.kind.value, value))
        row = await cur.fetchone()
        return row[0] if row else ""

    await cur.execute(
        f"{_INSERT} RETURNING id::text",
        (
            *entity,
            assertion.kind.value,
            value,
            _sources(assertion),
            created_by,
            assertion.changeset_id,
        ),
    )
    row = await cur.fetchone()
    return row[0] if row else ""


def _sources(assertion: Assertion) -> str | None:
    if not assertion.sources:
        return None
    return json.dumps([source.model_dump() for source in assertion.sources])


async def withdraw(
    cur,
    entity_type: EntityType,
    entity_id: str,
    field_path: str,
    kind: AssertionKind,
    withdrawn_by: str,
    reason: str | None = None,
    withdrawn_by_changeset_id: str | None = None,
) -> int:
    """Retract the current claim of this kind on a field, or 0 rows if nothing was live.

    `kind` is explicit since reject and accept can both be live on the same field at once, and
    only the winning (newest, non-withdrawn) row is touched. `withdrawn_by_changeset_id` is set
    only when a rollback changeset caused this; ordinary withdrawals leave it NULL."""
    await cur.execute(
        f"""
        UPDATE assertions
           SET withdrawn_at = now(), withdrawn_by = %s, withdrawn_reason = %s,
               withdrawn_by_changeset_id = %s
         WHERE id = (
             SELECT id FROM assertions
              WHERE entity_type = %s AND entity_id = %s AND field_path = %s
                AND kind = %s AND withdrawn_at IS NULL
              {LATEST_FIRST}
              LIMIT 1
         )
        """,
        (
            withdrawn_by,
            reason,
            withdrawn_by_changeset_id,
            entity_type.value,
            entity_id,
            field_path,
            kind.value,
        ),
    )
    return cur.rowcount


# "Which row currently wins," spelled as a predicate (not a Python fold) so a bulk rollback can
# touch exactly these rows in one statement. Matches `AssertionState.ACTIVE`. Requires the
# caller's query to alias the table `a` — unavoidable for a self-join.
_IS_ACTIVE = """
    a.withdrawn_at IS NULL
    AND a.id = (
        SELECT a2.id FROM assertions a2
         WHERE a2.entity_type = a.entity_type AND a2.entity_id = a.entity_id
           AND a2.field_path = a.field_path AND a2.kind = a.kind
           AND a2.withdrawn_at IS NULL
         ORDER BY a2.created_at DESC, a2.id DESC LIMIT 1
    )
"""


async def get_assertions_by_creator(
    cur, created_by: str, entity_type: EntityType
) -> list[dict]:
    """Every claim of one entity type this user ever made, anywhere, active or not — the
    history a "roll back this user" UI shows, with `withdrawn`/`superseded` letting the caller
    derive each row's `AssertionState` (only an ACTIVE one is a real rollback candidate).
    Not scoped to one jurisdiction. Joined through `people`, not the nullable
    `assertions.changeset_id`, same source `entity_jurisdiction.jurisdiction_for` reads.
    PERSON-specific."""
    await cur.execute(
        f"""
        SELECT a.id::text, a.entity_id::text, a.field_path, a.kind, a.value, p.jurisdiction_ocdid,
               a.created_at,
               a.withdrawn_at IS NOT NULL AS withdrawn,
               NOT ({_IS_ACTIVE}) AS superseded
        FROM assertions a
        JOIN people p ON p.id = a.entity_id
        WHERE a.entity_type = %s AND a.created_by = %s
        ORDER BY a.created_at DESC
        """,
        (entity_type.value, created_by),
    )
    columns = [column.name for column in cur.description or []]
    return [dict(zip(columns, row)) for row in await cur.fetchall()]


async def get_jurisdictions_for_assertions(
    cur, assertion_ids: list[str]
) -> dict[str, list[str]]:
    """These assertion ids, grouped by which jurisdiction each one's entity belongs to — lets a
    selection spanning several jurisdictions execute as several single-jurisdiction rollbacks.
    PERSON-specific, same reasoning as `get_assertions_by_creator`."""
    await cur.execute(
        """
        SELECT p.jurisdiction_ocdid, a.id::text
        FROM assertions a
        JOIN people p ON p.id = a.entity_id
        WHERE a.id = ANY(%s)
        """,
        (assertion_ids,),
    )
    grouped: dict[str, list[str]] = {}
    for jurisdiction_ocdid, assertion_id in await cur.fetchall():
        grouped.setdefault(jurisdiction_ocdid, []).append(assertion_id)
    return grouped


async def get_entity_ids_for_assertions(
    cur, entity_type: EntityType, assertion_ids: list[str]
) -> list[str]:
    """Which distinct entities these assertions are about — what a rollback republish needs to
    know whose derived state to recompute, having only a list of withdrawn assertion ids."""
    await cur.execute(
        "SELECT DISTINCT entity_id::text FROM assertions "
        "WHERE entity_type = %s AND id = ANY(%s)",
        (entity_type.value, assertion_ids),
    )
    rows = await cur.fetchall()
    return [row[0] for row in rows]


async def withdraw_assertions(
    cur,
    assertion_ids: list[str],
    withdrawn_by: str,
    withdrawn_by_changeset_id: str,
    reason: str | None = None,
) -> int:
    """Withdraw exactly these assertions, whichever are still ACTIVE — the one primitive a bulk
    rollback and a selective one share. Re-checks `_IS_ACTIVE` rather than trusting the caller's
    list is still current, since it may have been read moments earlier."""
    await cur.execute(
        f"""
        UPDATE assertions a
           SET withdrawn_at = now(), withdrawn_by = %s, withdrawn_reason = %s,
               withdrawn_by_changeset_id = %s
         WHERE a.id = ANY(%s) AND {_IS_ACTIVE}
        """,
        (withdrawn_by, reason, withdrawn_by_changeset_id, assertion_ids),
    )
    return cur.rowcount

async def create(assertion: Assertion, created_by: str) -> str:
    """Set one assertion, owning the connection. Returns its id.

    `created_by` is required: an assertion nobody made is not an assertion.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        assertion_id = await upsert(cur, assertion, created_by)
        await conn.commit()
    return assertion_id


async def create_all(claims: list[Assertion], created_by: str) -> None:
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
    """Every assertion about these rows, newest first, keyed by entity id.

    Carries who and when, which `asserted_values` does not — the editor tags each field with the
    person behind it.
    """
    if not entity_ids:
        return {}
    await cur.execute(
        """
        SELECT a.entity_id::text, a.id::text, a.field_path, a.kind, a.value, a.sources,
               a.created_at, a.created_by::text,
               COALESCE(u.username, u.email) AS created_by_name
        FROM assertions a
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


async def asserted_values(
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
        FROM assertions
        WHERE entity_type = %s AND entity_id::text = ANY(%s) AND withdrawn_at IS NULL
        {LATEST_FIRST}
        """,
        (entity_type.value, entity_ids),
    )
    asserted: dict[str, dict] = {}
    seen: set[tuple] = set()
    for entity_id, field_path, kind, value in await cur.fetchall():
        # Rows arrive newest first, so the first time a key is seen is its current winner —
        # everything after is history a newer claim has already superseded.
        key = (
            (entity_id, field_path, value)
            if _value_keyed(field_path, kind)
            else (entity_id, field_path)
        )
        if key in seen:
            continue
        seen.add(key)
        by_kind = asserted.setdefault(entity_id, {}).setdefault(
            field_path, {AssertionKind.ACCEPT: [], AssertionKind.REJECT: []}
        )
        by_kind[kind].append(value)
    return asserted
