"""What a person says about a membership.

Two verbs, not three (§2 of the projector plan): a membership either stands or is rejected.
`closed` is gone — "they left" and "the page was wrong" end a membership the same way, from the
claim's date, and history before it stays either way. The three-way request the editor still
sends maps onto them here until step 9's edit route replaces it.

The claim is what publish applies: the roster is derived from the facts, so nothing here writes
a row, and rolling the claim back re-derives without a special case.
"""

from database import memberships, people, projection
from database.database import get_pool
from schemas.posts import MembershipRemovalAssertion


async def set_assertion(
    membership_id: str,
    assertion: MembershipRemovalAssertion,
    user_id: str,
    reason: str | None = None,
    changeset_id: str | None = None,
) -> None:
    """Reject this membership, or take a rejection back, and rebuild.

    `closed` and `never_held` are the same claim: the editor still offers both, and step 9
    deletes the choice along with the enum.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        held = await memberships.membership_pair(cur, membership_id)
        if held is None:
            return
        person_id, post = held
        if assertion is MembershipRemovalAssertion.NONE:
            await memberships.withdraw_reject(cur, person_id, post.id, user_id)
        else:
            await memberships.reject(cur, person_id, post.id, user_id, reason, changeset_id)
        await projection.rebuild_from_facts(cur, post.jurisdiction_ocdid, changeset_id)
        await conn.commit()
