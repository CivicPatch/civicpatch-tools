from collections.abc import Iterable, Sequence
from datetime import datetime

from pydantic import BaseModel
from shared.schemas import Role
from shared.utils.taxonomy import Taxonomy

from core.projection.facts import Claim, Facts, PostKey, SourceRecord, latest_first
from core.projection.field_value import (
    list_value,
    other_names,
    scalar_value,
    source_urls,
)
from core.projection.membership_details import (
    MembershipSource,
    first_seen,
    label_details,
    last_seen,
    membership_sources,
)
from core.projection.memberships import (
    END_DATE,
    START_DATE,
    claimed_posts,
    post_accepts,
    is_edited,
    membership_date,
    membership_label,
    membership_state,
)
from core.projection.posts import records_by_post


class Membership(BaseModel, frozen=True):
    post_id: str
    first_seen_at: datetime
    last_seen_at: datetime
    label: str | None = None
    start_date: str | None = None
    end_date: str | None = None

    designations: tuple[str, ...] = ()
    unmatched_text: tuple[str, ...] = ()
    sources: tuple[MembershipSource, ...] = ()
    # Roles beyond the post's own, parsed from the labels (`membership_roles`).
    extra_roles: tuple[str, ...] = ()


class Person(BaseModel, frozen=True):
    # everything in people row, without jursidiction ocdids
    id: str
    name: str | None = None
    image: str | None = None
    cdn_image: str | None = None
    phones: tuple[str, ...] = ()
    emails: tuple[str, ...] = ()
    urls: tuple[str, ...] = ()
    other_names: tuple[str, ...] = ()
    source_urls: tuple[str, ...] = ()
    memberships: tuple[Membership, ...] = ()
    # A human has touched this person or one of their memberships.
    edited: bool = False


def derive_membership(
    members: Iterable[str],
    post: PostKey,
    own_records: Sequence[SourceRecord],
    facts: Facts,
    jurisdiction_ocdid: str,
    taxonomy: Taxonomy,
    roles: Sequence[Role],
) -> Membership:
    seen = [*own_records, *post_accepts(members, post, facts)]
    # The latest read's labels are the whole answer: a role or designation the page stopped
    # printing must not linger, which is what the upsert's `DO UPDATE` used to guarantee.
    latest_read = sorted(own_records, key=latest_first)[-1].changeset_id if own_records else None
    current = [record for record in own_records if record.changeset_id == latest_read]
    details = label_details(current, jurisdiction_ocdid, taxonomy, roles)
    return Membership(
        post_id=post.post_id,
        label=membership_label(members, post.post_id, facts),
        start_date=membership_date(members, post.post_id, START_DATE, own_records, facts),
        end_date=membership_date(members, post.post_id, END_DATE, own_records, facts),
        first_seen_at=first_seen(seen),
        last_seen_at=last_seen(seen),
        designations=details.designations,
        unmatched_text=details.unmatched_text,
        sources=membership_sources(own_records),
        extra_roles=details.extra_roles,
    )


def _newest_membership_fact(
    members: Iterable[str],
    post: PostKey,
    own_records: Sequence[SourceRecord],
    facts: Facts,
) -> SourceRecord | Claim:
    """The most recent fact that says this cluster holds this post: an accept, or a record
    listing them there. Every active post has one, which is what makes it active."""
    said = [*post_accepts(members, post, facts), *own_records]
    return max(said, key=latest_first)


def collapse_per_organization(
    members: Iterable[str],
    posts: Sequence[PostKey],
    by_post: dict[PostKey, list[SourceRecord]],
    facts: Facts,
) -> list[PostKey]:
    """The posts to keep, one per organization, which is all the projection allows.

    Records alone cannot break the rule: a cluster's records for one organization are parsed
    together and yield one post. A human can, by accepting a post the page does not list them
    in, and then whichever fact spoke last decides — so a hand-add nothing contradicts
    stands, and an accept the page has since answered lapses.
    """
    by_organization: dict[str, list[PostKey]] = {}
    for post in posts:
        by_organization.setdefault(post.organization_id, []).append(post)

    kept = []
    for organization_posts in by_organization.values():
        if not any(post_accepts(members, post, facts) for post in organization_posts):
            kept.extend(organization_posts)
            continue
        kept.append(
            max(
                organization_posts,
                key=lambda post: latest_first(
                    _newest_membership_fact(members, post, by_post.get(post, []), facts)
                ),
            )
        )
    return kept


def derive_person(
    person_id: str,
    members: Iterable[str],
    facts: Facts,
    jurisdiction_ocdid: str,
    taxonomy: Taxonomy,
    roles: Sequence[Role],
) -> Person:
    mine = [record for record in facts.records if record.person_id in members]
    by_post = records_by_post(mine, jurisdiction_ocdid, taxonomy, roles)
    candidates = sorted(set(by_post) | claimed_posts(members, facts), key=_by_post_id)

    active = [
        post
        for post in candidates
        if membership_state(members, post, by_post.get(post, []), facts)
    ]
    held = collapse_per_organization(members, active, by_post, facts)
    return Person(
        id=person_id,
        name=scalar_value(members, "name", facts),
        image=scalar_value(members, "image", facts),
        cdn_image=scalar_value(members, "cdn_image", facts),
        phones=list_value(members, "phones", facts),
        emails=list_value(members, "emails", facts),
        urls=list_value(members, "urls", facts),
        other_names=other_names(members, facts),
        source_urls=source_urls(members, facts),
        memberships=tuple(
            derive_membership(
                members, post, by_post.get(post, []), facts, jurisdiction_ocdid, taxonomy, roles
            )
            for post in sorted(held, key=_by_post_id)
        ),
        edited=is_edited(members, [post.post_id for post in candidates], facts),
    )


def _by_post_id(post: PostKey) -> str:
    return post.post_id
