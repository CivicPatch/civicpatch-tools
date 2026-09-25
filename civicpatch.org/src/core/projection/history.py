"""Membership history: the roster at each published changeset, diffed.

History is observed, not authored (§7): a term starts at the first changeset whose roster holds
the pair and ends at the first whose roster does not. No typed or scraped date moves a boundary.
"""

from collections.abc import Iterable
from datetime import datetime

from pydantic import BaseModel

from core.projection.roster import Roster


class Term(BaseModel, frozen=True):
    person_id: str
    post_id: str
    organization_id: str
    opened_at: datetime
    closed_at: datetime | None = None


def _held(roster: Roster) -> dict[tuple[str, str], str]:
    """`(person_id, post_id)` to the post's organization, for every membership held."""
    return {
        (person.id, membership.post.post_id): membership.post.organization_id
        for person in roster.people
        for membership in person.memberships
    }


def membership_terms(snapshots: Iterable[tuple[datetime, Roster]]) -> list[Term]:
    """`snapshots` is each published changeset's time and the roster derived as of it, oldest
    first. Returns every term, open ones with no `closed_at`, in start order."""
    closed: list[Term] = []
    open_terms: dict[tuple[str, str], Term] = {}
    for at, roster in snapshots:
        held = _held(roster)
        for key in [key for key in open_terms if key not in held]:
            closed.append(open_terms.pop(key).model_copy(update={"closed_at": at}))
        for (person_id, post_id), organization_id in held.items():
            if (person_id, post_id) not in open_terms:
                open_terms[(person_id, post_id)] = Term(
                    person_id=person_id,
                    post_id=post_id,
                    organization_id=organization_id,
                    opened_at=at,
                )
    terms = closed + list(open_terms.values())
    return sorted(terms, key=lambda term: (term.opened_at, term.person_id, term.post_id))
