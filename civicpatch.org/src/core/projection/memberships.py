"""Which posts a cluster holds, and what has been said about holding them.

A membership claim names its pair by a hash (`uuid5(person_id, post_id)`), so the fold cannot
read the post back out of `entity_id`. An `exists` claim therefore carries its post as its
`value` and locates itself: it is the claim on `(member, value)` for whichever member satisfies
`membership_id(member, value) == entity_id`.

Every other membership field is reached the other way round, through a post the cluster already
has from a record or an `exists` claim, by asking for `membership_id(member, post)`.
"""

from collections.abc import Iterable, Sequence

from pydantic import BaseModel
from shared.utils.membership_ids import membership_id

from core.projection.facts import (
    Claim,
    ClaimKind,
    EntityType,
    Facts,
    SourceRecord,
    latest_first,
)
from core.projection.reads import reads_of

EXISTS = "exists"
CLOSED = "closed"
LABEL = "label"

START_DATE = "start_date"
END_DATE = "end_date"

# Every field a human can claim about a membership, which is what "edited" asks about.
MEMBERSHIP_FIELDS = (EXISTS, CLOSED, LABEL, START_DATE, END_DATE)

LISTED_AFTER_CLOSE = "LISTED_AFTER_CLOSE"


class MembershipState(BaseModel, frozen=True):
    active: bool
    issue: str | None = None


def membership_claims(
    members: Iterable[str], post_id: str, field: str, facts: Facts
) -> list[Claim]:
    """This cluster's live claims about one field of one membership, oldest first."""
    ids = {membership_id(member, post_id) for member in members}
    return sorted(
        (
            claim
            for claim in facts.claims
            if claim.entity_type == EntityType.MEMBERSHIP
            and claim.entity_id in ids
            and claim.field_path == field
        ),
        key=latest_first,
    )


def claimed_posts(members: Iterable[str], facts: Facts) -> set[str]:
    """Posts a human named for this cluster, including rejects.
    membership_state decides the absent membership
    """

    posts = set()
    for claim in facts.claims:
        if claim.entity_type != EntityType.MEMBERSHIP:
            continue
        for member in members:
            if membership_id(member, claim.value) == claim.entity_id:
                posts.add(claim.value)

    return posts


def membership_label(members: Iterable[str], post_id: str, facts: Facts) -> str | None:
    """A human's name for this membership, if one stands."""
    labels = [
        claim
        for claim in membership_claims(members, post_id, LABEL, facts)
        if claim.kind == ClaimKind.ACCEPT
    ]
    return labels[-1].value if labels else None


def is_edited(members: Iterable[str], post_ids: Iterable[str], facts: Facts) -> bool:
    """Whether a human has touched this cluster or any of its memberships."""
    member_ids = set(members)
    if any(claim.entity_id in member_ids for claim in facts.claims):
        return True
    return any(
        membership_claims(members, post_id, field, facts)
        for post_id in post_ids
        for field in MEMBERSHIP_FIELDS
    )


def membership_state(
    members: Iterable[str],
    post_id: str,
    own_records: Sequence[SourceRecord],
    facts: Facts,
) -> MembershipState:
    """Whether this cluster holds this post, and what to ask a human about.

    A close stands until a user accepts. No evidence reopens it, not a continuous listing and
    not a gap in the reads, because a stale page must not undo somebody's "they are gone".
    """

    listed_now = False
    if own_records:
        organization_id = sorted(own_records, key=latest_first)[-1].organization_id
        reads = reads_of(organization_id, facts)
        listed_now = bool(reads) and any(
            record.changeset_id == reads[-1].changeset_id for record in own_records
        )

    claims = sorted(
        (
            membership_claims(members, post_id, EXISTS, facts)
            + membership_claims(members, post_id, CLOSED, facts)
        ),
        key=latest_first,
    )

    if not claims:
        return MembershipState(active=listed_now)

    newest = claims[-1]
    if newest.kind == ClaimKind.REJECT:
        return MembershipState(active=False)
    if newest.field_path == EXISTS:
        return MembershipState(active=True)
    return MembershipState(
        active=False, issue=LISTED_AFTER_CLOSE if listed_now else None
    )
