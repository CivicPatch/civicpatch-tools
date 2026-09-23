"""Which posts a cluster holds, and what has been said about holding them.

Holding a post is a claim about the *person*: `field_path = "posts"`, one claim per post,
accept or reject. So the fold reads who holds what without knowing a membership's row id, and
without reading `posts` — the loader resolves the claim's value into the post's key, which is
what says which organization the membership is in.

What a membership is called, and when it ran, is a claim about the membership itself, keyed by
`membership_id(person, post)` — reached from a post the cluster already has.
"""

from collections.abc import Iterable, Sequence

from shared.utils.membership_ids import membership_id

from core.people_edits import POSTS_FIELD
from core.projection.facts import (
    Claim,
    ClaimKind,
    EntityType,
    Facts,
    PostKey,
    SourceRecord,
    latest_first,
)
from core.projection.reads import Read, reads_of

MEMBERSHIP_LABEL_FIELD = "label"
MEMBERSHIP_START_DATE_FIELD = "start_date"
MEMBERSHIP_END_DATE_FIELD = "end_date"

# Every field a human can claim about a membership, which is what "edited" asks about.
MEMBERSHIP_FIELDS = (
    MEMBERSHIP_LABEL_FIELD,
    MEMBERSHIP_START_DATE_FIELD,
    MEMBERSHIP_END_DATE_FIELD,
)

def _posts_claims(members: Iterable[str], facts: Facts) -> list[Claim]:
    """Every live claim about which posts this cluster holds, oldest first. A claim naming a
    post that no longer exists has no key, and places nobody."""
    people = set(members)
    return sorted(
        (
            claim
            for claim in facts.claims
            if claim.entity_type == EntityType.PERSON
            and claim.entity_id in people
            and claim.field_path == POSTS_FIELD
        ),
        key=latest_first,
    )


def post_claims(members: Iterable[str], post: PostKey, facts: Facts) -> list[Claim]:
    """This cluster's live claims about whether it holds one post, oldest first."""
    return [claim for claim in _posts_claims(members, facts) if claim.post == post]


def post_accepts(members: Iterable[str], post: PostKey, facts: Facts) -> list[Claim]:
    """The accepts among them: a human put this cluster in this post."""
    return [
        claim
        for claim in post_claims(members, post, facts)
        if claim.kind == ClaimKind.ACCEPT
    ]


def claimed_posts(members: Iterable[str], facts: Facts) -> set[PostKey]:
    """Posts a human named for this cluster, of either kind. Naming one is not holding it:
    `membership_state` decides that."""
    return {
        claim.post for claim in _posts_claims(members, facts) if claim.post is not None
    }


def membership_claims(
    members: Iterable[str], post_id: str, field: str, facts: Facts
) -> list[Claim]:
    """This cluster's live claims about one field of one membership, oldest first. Keyed by
    `membership_id(person, post)`, which is the row's own id."""
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


def membership_label(members: Iterable[str], post_id: str, facts: Facts) -> str | None:
    """A human's name for this membership, if one stands."""
    labels = [
        claim
        for claim in membership_claims(members, post_id, MEMBERSHIP_LABEL_FIELD, facts)
        if claim.kind == ClaimKind.ACCEPT
    ]
    return labels[-1].value if labels else None


def membership_date(
    members: Iterable[str],
    post_id: str,
    field: str,
    own_records: Sequence[SourceRecord],
    facts: Facts,
) -> str | None:
    """`start_date` or `end_date`: the latest accept claim's value, else the latest record
    that has one."""
    accepts = [
        claim
        for claim in membership_claims(members, post_id, field, facts)
        if claim.kind == ClaimKind.ACCEPT
    ]
    if accepts:
        return accepts[-1].value

    dated = [
        record
        for record in sorted(own_records, key=latest_first)
        if getattr(record, field) is not None
    ]
    return getattr(dated[-1], field) if dated else None


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


def _listed_in(own_records: Sequence[SourceRecord], read: Read) -> bool:
    return any(record.changeset_id == read.changeset_id for record in own_records)


def membership_state(
    members: Iterable[str],
    post: PostKey,
    own_records: Sequence[SourceRecord],
    facts: Facts,
) -> bool:
    """Whether this cluster holds this post.

    An accept stands until withdrawn. A reject lasts until the organization is read again,
    and then the page decides.
    """
    claims = post_claims(members, post, facts)
    newest = claims[-1] if claims else None
    if newest and newest.kind == ClaimKind.ACCEPT:
        return True
    if not own_records:
        return False

    last_read = reads_of(post.organization_id, facts)[-1]
    lapsed = newest is not None and last_read.created_at > newest.created_at
    if newest and not lapsed:
        return False

    return _listed_in(own_records, last_read)
