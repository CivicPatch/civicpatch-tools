"""Who held which post, when: the roster at each moment the facts changed, diffed into rows.

Observed, not authored (§7): a row opens at the first snapshot whose roster holds the (person,
post) pair and closes at the first that does not. No typed or scraped date moves either end.
Holding a post twice is two rows.
"""

from collections.abc import Iterable
from datetime import datetime

from pydantic import BaseModel

from core.projection.people import Membership
from core.projection.roster import Roster


class MembershipRow(BaseModel, frozen=True):
    person_id: str
    # As it stood at the last snapshot that held it: a closed row keeps its label and dates.
    membership: Membership
    opened_at: datetime
    closed_at: datetime | None = None


def _held(roster: Roster) -> dict[tuple[str, str], Membership]:
    return {
        (person.id, membership.post.post_id): membership
        for person in roster.people
        for membership in person.memberships
    }


def _last_per_moment(
    snapshots: Iterable[tuple[datetime, Roster]],
) -> list[tuple[datetime, Roster]]:
    """Snapshots sharing a time collapse to the last: a pair cannot open twice at one moment."""
    collapsed: list[tuple[datetime, Roster]] = []
    for at, roster in snapshots:
        if collapsed and collapsed[-1][0] == at:
            collapsed[-1] = (at, roster)
        else:
            collapsed.append((at, roster))
    return collapsed


def membership_history(snapshots: Iterable[tuple[datetime, Roster]]) -> list[MembershipRow]:
    """`snapshots` is each moment and the roster derived as of it, oldest first. Returns every
    row, open ones with no `closed_at`, in the order they opened."""
    closed: list[MembershipRow] = []
    open_rows: dict[tuple[str, str], MembershipRow] = {}
    for at, roster in _last_per_moment(snapshots):
        held = _held(roster)
        for key in [key for key in open_rows if key not in held]:
            closed.append(open_rows.pop(key).model_copy(update={"closed_at": at}))
        for (person_id, post_id), membership in held.items():
            current = open_rows.get((person_id, post_id))
            open_rows[(person_id, post_id)] = MembershipRow(
                person_id=person_id,
                membership=membership,
                opened_at=current.opened_at if current else at,
            )
    return sorted(
        [*closed, *open_rows.values()],
        key=lambda row: (row.opened_at, row.person_id, row.membership.post.post_id),
    )
