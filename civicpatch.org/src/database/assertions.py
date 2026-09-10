"""Database queries for `assertions` — the field values a human has accepted or rejected.

Append-only: setting a value again inserts, it never overwrites, and withdrawing stamps a row
rather than deleting it. `created_by`/`created_at` on a row are therefore permanent — nothing
after the insert ever rewrites them. `current`/`asserted_values` resolve *what applies now* by
reading, not by the table holding only one row per field; `activity` is the narration, this is
the evidence.

Two entry points: `upsert` on a caller's cursor, `create` owning its own connection — a label
edit and the assertion protecting it must commit together.
"""

import json

from core.people_edits import LIST_FIELDS
from database.database import get_pool
from schemas.assertions import Assertion, AssertionKind, EntityType


def _value_keyed(field_path: str, kind: str) -> bool:
    """Only a scalar accept has one answer for the whole field; a reject (of either field
    shape) and a list field's accept are per-value, so distinct values coexist.

    Takes raw column values rather than an `Assertion`, so both a claim about to be written and
    a row already read back from the database can ask the same question the same way."""
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
    """The `_conflict_key`s already true, per `asserted_values` — which is to say: already
    the current winner, not merely present somewhere in history. A claim restating an old,
    since-superseded value is a real new claim, not a no-op.
    """
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
    """Retract the current claim of this kind on a field. Returns how many rows went — 0 if
    there was nothing live to retract.

    `kind` is explicit, not assumed `accept`: a retraction (189) is a REJECT — "this membership
    never held" — and reject and accept can both be live on the same field_path at once for
    different values, so the caller has to say which claim it means.

    Only the winning row: a claim already superseded by a later one is not the current answer,
    so stamping it too would claim a moderator retracted something a later claim had already
    replaced.

    `withdrawn_by_changeset_id` is the symmetric half of `changeset_id` — set only by a rollback
    changeset, marking which withdrawals it caused. Ordinary withdrawals (clearing a hand-set
    label back to derived) leave it NULL.
    """
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


# The same "which row currently wins" comparison `LATEST_FIRST`/`asserted_values` make by
# reading newest-first and taking the first unseen key — spelled as a predicate instead of a
# fold, because a bulk rollback needs to touch exactly these rows in one statement rather than
# rank a whole table in Python. Matches `core.assertion_lifecycle.AssertionState.ACTIVE`
# exactly: not withdrawn, and no newer non-withdrawn claim exists for the same key. Requires
# the caller's query to alias the table `a` — an exception to the alias-free rule for shared
# predicates, unavoidable for a self-join.
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


async def get_active_assertions_by_creator(
    cur, created_by: str, entity_type: EntityType
) -> list[dict]:
    """Every currently-ACTIVE claim of one entity type this user made, anywhere — the flat
    candidate list a "roll back this user" UI shows and selects from. Not scoped to one
    jurisdiction: nothing about picking what to undo needs a jurisdiction chosen up front, only
    execution does, and that's answered per selected id (`get_jurisdictions_for_assertions`),
    not by the listing.

    Joined through `people`, not `changesets` — an assertion's jurisdiction is a fact about the
    entity it's about, same source `entity_jurisdiction.jurisdiction_for` reads for one row at a
    time; `changeset_id` is nullable (pre-188 rows, direct asserts) and would silently drop
    them. PERSON-specific, matching every other PERSON-only assumption in this feature.
    """
    await cur.execute(
        f"""
        SELECT a.id::text, a.entity_id::text, a.field_path, a.value, p.jurisdiction_ocdid
        FROM assertions a
        JOIN people p ON p.id = a.entity_id
        WHERE a.entity_type = %s AND a.created_by = %s AND {_IS_ACTIVE}
        ORDER BY a.created_at DESC
        """,
        (entity_type.value, created_by),
    )
    columns = [column.name for column in cur.description or []]
    return [dict(zip(columns, row)) for row in await cur.fetchall()]


async def get_jurisdictions_for_assertions(
    cur, assertion_ids: list[str]
) -> dict[str, list[str]]:
    """These assertion ids, grouped by which jurisdiction each one's entity belongs to — what
    lets a rollback selection spanning more than one jurisdiction execute as several
    single-jurisdiction rollbacks without the caller ever needing to group them itself.
    PERSON-specific, same reasoning as `get_active_assertions_by_creator`."""
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
    """Withdraw exactly these assertions, whichever are still ACTIVE. Returns how many went.

    The one primitive a bulk rollback (every id a listing query just returned) and a selective
    one (whichever ids a reviewer checked) share — bulk is the unfiltered case of selective, not
    a separate code path. Re-checks `_IS_ACTIVE` rather than trusting the caller's list is still
    current, since it may have been read moments earlier.
    """
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
               COALESCE(u.display_name, u.email) AS created_by_name
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
    """`{entity_id: {field: {"accept": [...], "reject": [...]}}}` for these rows — only the
    claim that currently applies. Both kinds together, because applying them is
    `(scraped ∪ accepted) − rejected`. A row nobody has judged is absent rather than empty.

    History is append-only, so a field can hold many rows over time. Withdrawn ones never
    apply. Of what remains: a scalar accept can only have one current answer, so only the most
    recent counts — an older, superseded value is not returned even though its row still
    exists. A list field's accept and reject are per *value*, so each value's own most recent
    claim wins independently of the others: a number can be accepted, then rejected, then
    accepted again, and only the last of those is live — the same value never appears on both
    sides at once, which is what makes the merge in `with_asserted_values` sound.
    """
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
