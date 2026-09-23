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


# Mirrored, with `MembershipPost` and `ProposedChange`, by frontend `schemas/membership-proposal.ts`.
class MembershipDisposition(str, Enum):
    UNCHANGED = "unchanged"
    NEW = "new"
    MOVED = "moved"
    ABSENT = "absent"


class MembershipPost(BaseModel):
    """The post a membership is in, or would be in. `id` is None for one a scrape would create."""

    id: str | None = None
    role_id: str
    role_label: str
    division_ocdid: str
    # The name a human gave the post, else `derive_post_label`'s. Display only; never compared.
    label: str
    # A roster omitting an untracked post means nothing, so its holder going missing is recorded
    # but never queued for a human.
    meta_is_tracked: bool = True


class ExistingMembership(BaseModel):
    """One open membership."""

    id: str
    jurisdiction_ocdid: str
    person_id: str
    organization_id: str
    post: MembershipPost
    membership_label: str | None = None


def ids_by_person_and_organization(
    held: list[ExistingMembership],
) -> dict[tuple[str, str], str]:
    return {
        (membership.person_id, membership.organization_id): membership.id
        for membership in held
    }


class ProposedChange(BaseModel):
    """What a scrape would do to one person's membership in one organization."""

    person_id: str
    organization_id: str
    disposition: MembershipDisposition
    # For ABSENT, the post they would leave. The caller fills `post.id` and its asserted name
    # when the post exists.
    post: MembershipPost
    membership_label: str | None = None
    # MOVED only: the post they would leave.
    from_post: MembershipPost | None = None


def _derived_post(post: DerivedPost) -> MembershipPost:
    return MembershipPost(
        role_id=post.role_id,
        role_label=post.role_label,
        division_ocdid=post.division_ocdid,
        label=derive_post_label(post.role_label, post.division_ocdid),
    )


def _disposition(held: ExistingMembership | None, post: DerivedPost) -> MembershipDisposition:
    if held is None:
        return MembershipDisposition.NEW
    if (held.post.role_id, held.post.division_ocdid) == (post.role_id, post.division_ocdid):
        return MembershipDisposition.UNCHANGED
    return MembershipDisposition.MOVED


def propose(
    derived: list[DerivedPost],
    existing: list[ExistingMembership],
    organizations_read: list[str],
) -> list[ProposedChange]:
    """Each derived membership against what the person holds in that same organization.

    `organizations_read` bounds the absences, the same bound publish closes within
    (`publications._organizations_to_close_in`): a scrape that read only the council page proposes
    nothing about a school board member. Without it, review shows a departure publish will not make.
    """
    # An empty scrape proposes nothing rather than marking everyone absent: that is a failed
    # scrape more often than a dissolved organization.
    if not derived:
        return []

    held_by_person_and_organization = {
        (membership.person_id, membership.organization_id): membership for membership in existing
    }
    seen: set[str] = set()
    changes: list[ProposedChange] = []

    for post in derived:
        for member in post.members:
            seen.add(member.person_id)
            held = held_by_person_and_organization.get((member.person_id, post.organization_id))
            disposition = _disposition(held, post)
            changes.append(
                ProposedChange(
                    person_id=member.person_id,
                    organization_id=post.organization_id,
                    disposition=disposition,
                    post=_derived_post(post),
                    membership_label=member.membership_label,
                    from_post=held.post if held and disposition is MembershipDisposition.MOVED else None,
                )
            )

    # Sourced from what we hold, not from the scrape — there is no incoming row to hang a
    # disappearance on.
    read = set(organizations_read)
    changes.extend(
        ProposedChange(
            person_id=membership.person_id,
            organization_id=membership.organization_id,
            disposition=MembershipDisposition.ABSENT,
            post=membership.post,
        )
        for membership in existing
        if membership.person_id not in seen and membership.organization_id in read
    )
    return changes


def surfaces_for_review(change: ProposedChange) -> bool:
    return change.disposition is not MembershipDisposition.UNCHANGED


def nothing_to_review(changes: list[ProposedChange]) -> bool:
    return bool(changes) and not any(surfaces_for_review(change) for change in changes)
