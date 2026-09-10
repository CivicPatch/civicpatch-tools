"""Rolling back a user's hand-made assertions: withdraw them under a freshly minted rollback
changeset per jurisdiction touched, then republish so the withdrawal is actually visible.

Scoped to `EntityType.PERSON` only (`POST`/`MEMBERSHIP` need a recompute step that doesn't
exist yet, see `.scratch/TODO.md`) and to field values, not additions — a hand-added person's
sighting re-seats them via their own label regardless of withdrawn assertions, so undoing an
addition needs the sighting invalidated, which nothing here does.
"""

from core.people_edits import with_asserted_values
from database import assertions, changesets as changesets_db
from database.database import get_pool
from database.people import get_people, get_people_by_ids
from schemas.assertions import EntityType
from schemas.rollback import RollbackCandidate
from services.publish import publish_people
from services.roster import origin_roster_for
from shared.utils.id_utils import make_id


class NothingToRollBack(Exception):
    """The target has no active effect left to undo — "Only what is still in effect"."""


def _entity_label(entity_id: str, people: dict) -> str:
    """The person's name, or the bare id if they've since been deleted."""
    person = people.get(entity_id)
    return person.name if person else entity_id


async def list_rollback_candidates(created_by: str) -> list[RollbackCandidate]:
    """Every currently-active `PERSON` claim this user made, anywhere. Empty means nothing to
    show, not an error — `rollback_assertions` is what raises once a selection is acted on."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        rows = await assertions.get_active_assertions_by_creator(cur, created_by, EntityType.PERSON)
    people = await get_people_by_ids(list({row["entity_id"] for row in rows}))
    return [
        RollbackCandidate(
            assertion_id=row["id"],
            entity_id=row["entity_id"],
            entity_label=_entity_label(row["entity_id"], people),
            field_path=row["field_path"],
            value=row["value"],
            jurisdiction_ocdid=row["jurisdiction_ocdid"],
        )
        for row in rows
    ]


async def _republish(
    jurisdiction_ocdid: str,
    rollback_changeset_id: str,
    affected_entity_ids: list[str],
    user_id: str,
) -> None:
    """Make a withdrawal visible. The live roster already has the withdrawn assertion baked
    into its stored columns, so only the affected people are recomputed, from their earliest
    sighting; everyone else's row is already correct and comes through untouched."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        asserted = await assertions.asserted_values(
            cur, EntityType.PERSON, affected_entity_ids
        )
    origin = {
        person["id"]: with_asserted_values(person, asserted.get(person["id"], {}))
        for person in await origin_roster_for(affected_entity_ids, jurisdiction_ocdid)
    }
    people = [
        origin.get(person["id"], person)
        for person in await get_people(jurisdiction_ocdid=jurisdiction_ocdid)
    ]
    await publish_people(rollback_changeset_id, jurisdiction_ocdid, people, user_id)


async def _rollback_in_jurisdiction(
    assertion_ids: list[str], jurisdiction_ocdid: str, user_id: str, reason: str | None
) -> int:
    """Withdraw exactly these assertions (all in one jurisdiction — a rollback changeset
    belongs to exactly one), then republish. Returns how many were withdrawn.

    Raises `NothingToRollBack` if none of them are still ACTIVE — checked by the withdraw's own
    rowcount rather than trusting the caller's list is still current, so the rollback changeset
    this mints is never left published with nothing behind it: the `raise` happens before
    `commit()`, so Postgres rolls the whole attempt back, mint included.
    """
    pool = await get_pool()
    rollback_id = make_id()
    async with pool.connection() as conn, conn.cursor() as cur:
        await changesets_db.register_rollback_changeset(
            cur, rollback_id, jurisdiction_ocdid, user_id
        )
        withdrawn = await assertions.withdraw_assertions(
            cur, assertion_ids, user_id, rollback_id, reason
        )
        if not withdrawn:
            raise NothingToRollBack(assertion_ids)
        affected_entity_ids = await assertions.get_entity_ids_for_assertions(
            cur, EntityType.PERSON, assertion_ids
        )
        await conn.commit()

    await _republish(jurisdiction_ocdid, rollback_id, affected_entity_ids, user_id)
    return withdrawn


async def rollback_assertions(
    assertion_ids: list[str], user_id: str, reason: str | None = None
) -> int:
    """Withdraw exactly these assertions, then republish. Returns how many were withdrawn.

    The one executor — a bulk rollback (every id `list_rollback_candidates` returned) and a
    selective one (whichever ids a reviewer checked in the UI) are both just callers choosing
    what to pass; nothing here tells them apart, and neither has to pick a jurisdiction first.
    Grouped by jurisdiction internally (`get_jurisdictions_for_assertions`) since a rollback
    changeset belongs to exactly one, and minted once per group that still has anything active.

    Raises `NothingToRollBack` if nothing across the whole selection was still active to undo.
    """
    if not assertion_ids:
        raise NothingToRollBack(assertion_ids)
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        by_jurisdiction = await assertions.get_jurisdictions_for_assertions(cur, assertion_ids)

    total = 0
    for jurisdiction_ocdid, ids in by_jurisdiction.items():
        try:
            total += await _rollback_in_jurisdiction(ids, jurisdiction_ocdid, user_id, reason)
        except NothingToRollBack:
            continue
    if not total:
        raise NothingToRollBack(assertion_ids)
    return total
