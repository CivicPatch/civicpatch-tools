"""Every claim a person carries, for the editor's per-field tags.

Filed here rather than with the proposal layer it grew up in: a claim is not a proposal, and
this outlives the layer's deletion.
"""

import asyncio

from database import assertions
from database import memberships as memberships_db
from database.database import get_pool
from schemas.assertions import EntityType


async def assertions_for_people(person_ids: list[str]) -> dict[str, list[dict]]:
    """Every assertion about these people, for the editor's per-field tags.

    A membership label's assertion is filed against the membership, not the person
    (`set_post_label`) — merged in here, under the person it belongs to, so the editor's
    per-field lock lookup never has to know the label lives on a different entity.
    """
    if not person_ids:
        return {}
    pool = await get_pool()

    async def _person_claims() -> dict[str, list[dict]]:
        async with pool.connection() as conn, conn.cursor() as cur:
            return await assertions.list_for_entities(
                cur, EntityType.PERSON, person_ids
            )

    async def _open_memberships() -> list[dict]:
        async with pool.connection() as conn, conn.cursor() as cur:
            return await memberships_db.open_memberships_for_persons(cur, person_ids)

    # Independent reads — neither needs the other's result — so they run concurrently rather
    # than as two round trips on one connection.
    claims, open_memberships = await asyncio.gather(
        _person_claims(), _open_memberships()
    )
    if not open_memberships:
        return claims
    membership_ids = [row["id"] for row in open_memberships]
    person_by_membership = {row["id"]: row["person_id"] for row in open_memberships}
    async with pool.connection() as conn, conn.cursor() as cur:
        membership_claims = await assertions.list_for_entities(
            cur, EntityType.MEMBERSHIP, membership_ids
        )
    for membership_id, membership_assertions in membership_claims.items():
        person_id = person_by_membership[membership_id]
        claims.setdefault(person_id, []).extend(membership_assertions)
    return claims
