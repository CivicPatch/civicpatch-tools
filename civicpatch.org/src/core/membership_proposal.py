"""What a scrape would change about who holds what.

Pure. The derivation says who the scrape found; `memberships` says who we already have. The
difference is the review queue, and it is a diff rather than a list because a roster that
restates what we know asks nobody for anything.

Posts are compared on `(organization, role_id, division_ocdid)`, not on id: the derivation describes posts
that may not exist yet, so an id is not available to compare on.
"""

from enum import Enum

from pydantic import BaseModel

from core.membership_label import derive_post_label
from core.post_derivation import DerivedPost


class Disposition(str, Enum):
    UNCHANGED = "unchanged"
    NEW = "new"
    MOVED = "moved"
    ABSENT = "absent"


class ExistingMembership(BaseModel):
    """One open membership, with its post's role and division."""

    id: str
    jurisdiction_ocdid: str
    person_id: str
    organization_id: str
    post_id: str
    label: str | None = None
    designations: list[str] = []
    role_id: str
    role_label: str = ""
    division_ocdid: str
    # `posts.meta_is_tracked`. A roster omitting an untracked post means nothing, so its holder
    # going missing is recorded but never queued for a human.
    meta_unmatched_text: list[str] = []
    meta_is_tracked: bool = True


def ids_by_person_and_organization(
    held: list[ExistingMembership],
) -> dict[tuple[str, str], str]:
    return {
        (membership.person_id, membership.organization_id): membership.id
        for membership in held
    }


class ProposedChange(BaseModel):
    person_id: str
    organization_id: str
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
    # Where they were, named. Derived here rather than looked up: the held membership already
    # carries the role label and division, and the reviewer needs both ends of a move in one
    # sentence — the card no longer annotates the Post field with a `was`.
    from_post_label: str = ""
    meta_is_tracked: bool = True


def _disposition(held: ExistingMembership | None, post: DerivedPost) -> Disposition:
    if held is None:
        return Disposition.NEW
    if (held.role_id, held.division_ocdid) == (post.role_id, post.division_ocdid):
        return Disposition.UNCHANGED
    return Disposition.MOVED


def propose(
    derived: list[DerivedPost],
    existing: list[ExistingMembership],
) -> list[ProposedChange]:
    """Each derived membership against what the person holds in that same organization."""
    # An empty scrape proposes nothing rather than marking everyone absent — the same guard
    # `close_absent` makes, for the same reason: that is a failed scrape, not a dissolved body.
    if not derived:
        return []

    held_by_person_and_organization = {
        (row.person_id, row.organization_id): row for row in existing
    }
    seen: set[str] = set()
    changes: list[ProposedChange] = []

    for post in derived:
        for member in post.members:
            seen.add(member.person_id)
            held = held_by_person_and_organization.get(
                (member.person_id, post.organization_id)
            )
            disposition = _disposition(held, post)
            moved_from = held if disposition is Disposition.MOVED else None
            changes.append(
                ProposedChange(
                    person_id=member.person_id,
                    organization_id=post.organization_id,
                    disposition=disposition,
                    role_id=post.role_id,
                    role_label=post.role_label,
                    division_ocdid=post.division_ocdid,
                    post_label=derive_post_label(post.role_label, post.division_ocdid),
                    label=member.label,
                    from_post_id=moved_from.post_id if moved_from else None,
                    from_post_label=derive_post_label(
                        moved_from.role_label, moved_from.division_ocdid
                    )
                    if moved_from
                    else "",
                )
            )

    # Sourced from what we hold, not from the scrape — there is no incoming row to hang a
    # disappearance on. Per person until step 9 closes per organization.
    changes.extend(
        ProposedChange(
            person_id=row.person_id,
            organization_id=row.organization_id,
            disposition=Disposition.ABSENT,
            role_id=row.role_id,
            role_label=row.role_label,
            division_ocdid=row.division_ocdid,
            post_label=derive_post_label(row.role_label, row.division_ocdid),
            from_post_id=row.post_id,
            meta_is_tracked=row.meta_is_tracked,
        )
        for row in existing
        if row.person_id not in seen
    )
    return changes


def surfaces_for_review(change: ProposedChange) -> bool:
    return change.disposition is not Disposition.UNCHANGED


def nothing_to_review(changes: list[ProposedChange]) -> bool:
    return bool(changes) and not any(surfaces_for_review(change) for change in changes)
