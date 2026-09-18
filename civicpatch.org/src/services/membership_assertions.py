"""What a person says about a membership, and about whether someone is an official here at all.

Assertions, not writes: each one is an `assertions` row that publish applies (`close_claimed`,
`close_for_people_rejected_here`) and that withdrawing takes back, so the published roster stays a
derivation of evidence plus live claims and rollback needs no per-action undo.

The three a reviewer picks between, and what each means:

  none         no assertion                      nothing filed; either below withdrawn
  closed       stop listing them here            membership `closed_at` accepted
  never_held   the membership was never true     membership existence rejected (`retract`)

`closed_at` is ours and `end_date` is the source's, so closing says we stopped carrying the
membership, not that somebody knows the term ended on a date. A claim about the term itself is an
`end_date` assertion, which is a different act nobody has asked for yet.

They contradict each other, so setting one withdraws the other: `set_assertion` takes the choice,
rather than four endpoints that could file both at once.

Not a member is the person-level version: publish closes every membership of theirs in the
jurisdiction. Deleting the person row is none of these, because it destroys history rather than
claiming anything, which is why it lives in `people.delete_person` behind a stricter permission.
"""

from database import memberships, people
from database.database import get_pool
from schemas.posts import MembershipRemovalAssertion


async def set_assertion(
    membership_id: str,
    assertion: MembershipRemovalAssertion,
    user_id: str,
    reason: str | None = None,
    changeset_id: str | None = None,
) -> None:
    """File the assertion somebody chose, and withdraw the one it contradicts."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        if assertion is MembershipRemovalAssertion.CLOSED:
            await memberships.reinstate(cur, membership_id, user_id)
            await memberships.assert_closed_at(
                cur, membership_id, user_id, reason, changeset_id
            )
        elif assertion is MembershipRemovalAssertion.NEVER_HELD:
            await memberships.withdraw_closed_at(cur, membership_id, user_id)
            await memberships.retract(cur, membership_id, user_id, reason, changeset_id)
        else:
            await memberships.withdraw_closed_at(cur, membership_id, user_id)
            await memberships.reinstate(cur, membership_id, user_id)


async def assert_not_a_member(
    person_id: str, user_id: str, reason: str | None = None, changeset_id: str | None = None
) -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        return await people.assert_not_a_member(
            cur, person_id, user_id, reason, changeset_id
        )


async def withdraw_not_a_member(person_id: str, user_id: str) -> int:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        return await people.withdraw_not_a_member(cur, person_id, user_id)
