from collections.abc import Iterable, Sequence

from pydantic import BaseModel
from shared.schemas import Role
from shared.utils.taxonomy import Taxonomy

from core.projection.facts import Facts
from core.projection.field_value import (
    list_value,
    other_names,
    scalar_value,
    source_urls,
)
from core.projection.memberships import (
    claimed_posts,
    is_edited,
    membership_label,
    membership_state,
)
from core.projection.posts import records_by_post


class Membership(BaseModel, frozen=True):
    post_id: str
    label: str | None = None


class PersonIssue(BaseModel, frozen=True):
    post_id: str
    issue: str


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
    issues: tuple[PersonIssue, ...] = ()


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
    post_ids = sorted(set(by_post.keys()) | set(claimed_posts(members, facts)))
    memberships = []
    issues = []
    for post_id in post_ids:
        state = membership_state(members, post_id, by_post.get(post_id, []), facts)
        if state.active:
            memberships.append(
                Membership(
                    post_id=post_id, label=membership_label(members, post_id, facts)
                )
            )

        if state.issue:
            issues.append(PersonIssue(post_id=post_id, issue=state.issue))

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
        memberships=tuple(memberships),
        edited=is_edited(members, post_ids, facts),
        issues=tuple(issues),
    )
