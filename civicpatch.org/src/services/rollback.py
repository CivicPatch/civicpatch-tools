"""Rolling back a changeset: withdraw every live fact it filed, under one born-published
rollback changeset, then re-derive the jurisdiction.

The unit is the changeset, not the claim (§17). That is what makes an addition undoable: a
hand-added person's own source record is one of the facts withdrawn, where the old per-claim
rollback left it standing and the fold re-derived them from it. Batch and user-since are the
other two sizes, and both are this call in a loop.

X stays published. Rollback is not a state, so undo is rolling back the rollback.
"""

from datetime import datetime, timedelta, timezone

from core.projection.facts import EntityType, Facts
from core.projection.live_facts import live_facts
from database import changesets as changesets_db
from database.claims import withdraw_facts
from database.database import get_pool
from database.facts import load_facts
from schemas.rollback import RollbackCandidate
from services.publish import publish_roster
from shared.utils.id_utils import make_id

CANDIDATE_WINDOW = timedelta(days=7)


class NothingToRollBack(Exception):
    """Every fact this changeset filed is already withdrawn --- "only what is still in effect"."""


async def list_user_changesets(created_by: str) -> list[RollbackCandidate]:
    """This user's published changesets from the last week: what a rollback screen offers.

    Empty means nothing to show rather than an error. `rollback_changeset` is what refuses once
    a selection is acted on, because whether a changeset still has live facts is a question
    about the facts, not about the listing.
    """
    since = datetime.now(timezone.utc) - CANDIDATE_WINDOW
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        rows = await changesets_db.by_creator_since(cur, created_by, since)
    return [
        RollbackCandidate(
            changeset_id=row["id"],
            kind=row["kind"],
            jurisdiction_ocdid=row["jurisdiction_ocdid"],
            jurisdiction_name=row["jurisdiction_name"] or row["jurisdiction_ocdid"],
            comment=row["comment"],
            published_at=row["published_at"],
        )
        for row in rows
    ]


def _facts_of(facts: Facts, changeset_id: str) -> dict[EntityType, list[str]]:
    """This changeset's own facts, by the entity type a withdraw would name them with.

    `facts` is already `live_facts`, so anything a standing withdraw points at is absent --- which
    is what makes rolling the same changeset back twice write nothing the second time, without a
    second definition of "still in effect". A withdraw is a claim row, so it is withdrawn as one.
    """
    return {
        EntityType.SOURCE_RECORD: [
            record.id for record in facts.records if record.changeset_id == changeset_id
        ],
        EntityType.SOURCE_PAGE: [
            read.id for read in facts.reads if read.changeset_id == changeset_id
        ],
        EntityType.CLAIM: [
            claim.id
            for claim in (*facts.claims, *facts.withdraws)
            if claim.changeset_id == changeset_id
        ],
    }


async def rollback_changeset(changeset_id: str, user_id: str, comment: str) -> int:
    """Withdraw every live fact of one changeset, then re-derive. Returns how many were withdrawn.

    One transaction for the changeset row and the withdraws, so a published rollback can never
    exist having changed nothing. The re-derive is outside it: `publish_roster` folds the facts
    as they now stand, and the withdraws are already committed by then.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        ocdids = await changesets_db.jurisdictions_for_changesets([changeset_id])
        jurisdiction_ocdid = ocdids.get(changeset_id)
        if not jurisdiction_ocdid:
            raise NothingToRollBack(changeset_id)
        facts = await load_facts(cur, jurisdiction_ocdid, datetime.now(timezone.utc))

    by_type = _facts_of(live_facts(facts), changeset_id)
    total = sum(len(ids) for ids in by_type.values())
    if not total:
        raise NothingToRollBack(changeset_id)

    rollback_id = make_id()
    async with pool.connection() as conn, conn.cursor() as cur:
        await changesets_db.register_rollback_changeset(
            cur, rollback_id, jurisdiction_ocdid, user_id, comment
        )
        for entity_type, entity_ids in by_type.items():
            await withdraw_facts(
                cur, entity_type, entity_ids, user_id, rollback_id, comment
            )
        await conn.commit()

    await publish_roster(
        jurisdiction_ocdid=jurisdiction_ocdid,
        changeset_id=rollback_id,
        resolved_by_user_id=user_id,
    )
    return total


async def rollback_changesets(
    changeset_ids: list[str], user_id: str, comment: str
) -> int:
    """Several changesets in one action --- a batch, or every changeset by a user since some time.

    Serial rather than gathered: each rolls back one jurisdiction and re-derives it, and two
    rollbacks of the same jurisdiction must not interleave. One already-undone changeset does not
    stop the rest. Raises only if nothing anywhere in the selection was still in effect.
    """
    if not changeset_ids:
        raise NothingToRollBack(changeset_ids)
    total = 0
    for changeset_id in changeset_ids:
        try:
            total += await rollback_changeset(changeset_id, user_id, comment)
        except NothingToRollBack:
            continue
    if not total:
        raise NothingToRollBack(changeset_ids)
    return total
