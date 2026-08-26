"""What a scrape would change about who holds what.

Pure. The derivation says who the scrape found; `memberships` says who we already have. The
difference is the review queue, and it is a diff rather than a list because a roster that
restates what we know asks nobody for anything.

Posts are compared on `(role_id, division_ocdid)`, not on id: the derivation describes posts
that may not exist yet, so an id is not available to compare on.
"""

from enum import Enum

from pydantic import BaseModel

from core.membership_label import rendered_post_label
from core.post_derivation import DerivedPost


class Disposition(str, Enum):
    UNCHANGED = "unchanged"
    NEW = "new"
    MOVED = "moved"
    ABSENT = "absent"


class ExistingMembership(BaseModel):
    person_id: str
    post_id: str
    role_id: str
    role_label: str = ""
    division_ocdid: str
    post_label: str | None = None
    # `posts._is_tracked`. A roster omitting an untracked post means nothing, so its holder
    # going missing is recorded but never queued for a human.
    is_tracked: bool = True


class ProposedChange(BaseModel):
    person_id: str
    disposition: Disposition
    role_id: str
    role_label: str = ""
    division_ocdid: str
    post_label: str
    label: str | None = None
    # The seat they would land in, when it already exists as a row. Filled in by the caller,
    # not here: `propose` works in identities and knows no ids. It is what lets the editor
    # show the derived seat as the Post field's current value — displayed, never stored,
    # because storing it would freeze this derivation into the person and a parser fix could
    # never reach them.
    post_id: str | None = None
    # Where they were, for a move or a disappearance.
    from_post_id: str | None = None
    is_tracked: bool = True


def _seat(role_id: str, division_ocdid: str) -> tuple[str, str]:
    return (role_id, division_ocdid)


def propose(
    derived: list[DerivedPost], existing: list[ExistingMembership]
) -> list[ProposedChange]:
    # An empty scrape proposes nothing rather than marking everyone absent — the same guard
    # `close_absent` makes, for the same reason: that is a failed scrape, not a dissolved body.
    if not derived:
        return []

    by_person = {row.person_id: row for row in existing}
    seen: set[str] = set()
    changes: list[ProposedChange] = []

    for post in derived:
        for member in post.members:
            seen.add(member.person_id)
            held = by_person.get(member.person_id)
            if held is None:
                disposition = Disposition.NEW
            elif _seat(held.role_id, held.division_ocdid) == _seat(
                post.role_id, post.division_ocdid
            ):
                disposition = Disposition.UNCHANGED
            else:
                disposition = Disposition.MOVED
            changes.append(
                ProposedChange(
                    person_id=member.person_id,
                    disposition=disposition,
                    role_id=post.role_id,
                    role_label=post.role_label,
                    division_ocdid=post.division_ocdid,
                    post_label=rendered_post_label(
                        None, post.role_label, post.division_ocdid
                    ),
                    label=member.label,
                    from_post_id=held.post_id
                    if held and disposition is Disposition.MOVED
                    else None,
                )
            )

    # Sourced from what we hold, not from the scrape — there is no incoming row to hang a
    # disappearance on, which is why it cannot be found by walking `derived` alone.
    changes.extend(
        ProposedChange(
            person_id=row.person_id,
            disposition=Disposition.ABSENT,
            role_id=row.role_id,
            role_label=row.role_label,
            division_ocdid=row.division_ocdid,
            post_label=rendered_post_label(
                row.post_label, row.role_label, row.division_ocdid
            ),
            from_post_id=row.post_id,
            is_tracked=row.is_tracked,
        )
        for row in existing
        if row.person_id not in seen
    )
    return changes


def surfaces_for_review(change: ProposedChange) -> bool:
    return change.disposition is not Disposition.UNCHANGED


def nothing_to_review(changes: list[ProposedChange]) -> bool:
    return bool(changes) and not any(surfaces_for_review(change) for change in changes)
