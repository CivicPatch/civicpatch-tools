"""Which post a person's records in one organization point at, and what else those labels
said while we were reading them.

A post is `(organization, role, division)`. One read of the labels answers both questions, so
`parse_labels` is the only place `derive_roles` runs for a membership.
"""

from collections import defaultdict
from collections.abc import Mapping, Sequence

from pydantic import BaseModel
from shared.utils.taxonomy import UNMATCHED_ROLE_ID, Taxonomy

from core.membership_label import MembershipLabel, render
from core.people_roles import (
    DerivedRoles,
    derive_roles,
    has_division,
    is_elected_by_voters,
    names_only_elected_by_members_roles,
)
from core.projection.facts import PostKey, SourceRecord, latest_first
from core.projection.membership_details import LabelDetails, MembershipRecords


class PostRole(BaseModel, frozen=True):
    """The role of an organization's posts elected by voters, read off its people's labels."""

    role: str
    has_divisions: bool


PostRoles = Mapping[str, PostRole]


def post_role_holders(
    records: Sequence[SourceRecord], jurisdiction_ocdid: str, taxonomy: Taxonomy
) -> dict[tuple[str, str], list[DerivedRoles]]:
    """Per organization and role elected by voters, each holder's newest labels."""
    holders: dict[tuple[str, str], list[DerivedRoles]] = defaultdict(list)
    for (organization_id, _), batch in _batches_by_person(records).items():
        derived = derive_roles(_labels(batch), jurisdiction_ocdid, taxonomy)
        if derived.role is None or not is_elected_by_voters(derived.role, taxonomy):
            continue
        holders[(organization_id, derived.role)].append(derived)
    return holders


def organization_post_roles(
    records: Sequence[SourceRecord], jurisdiction_ocdid: str, taxonomy: Taxonomy
) -> dict[str, PostRole]:
    """Per organization, the role elected by voters that the most people hold, so a lone mayor
    beside four council members is not it; ties go to the higher priority."""
    holders = post_role_holders(records, jurisdiction_ocdid, taxonomy)

    def most_held_first(key: tuple[str, str]) -> tuple:
        _, role = key
        return (-len(holders[key]), taxonomy.role_priority.get(role, 1_000_000), role)

    post_roles: dict[str, PostRole] = {}
    for organization_id, role in sorted(holders, key=most_held_first):
        if organization_id in post_roles:
            continue
        has_divisions = any(has_division(derived) for derived in holders[(organization_id, role)])
        post_roles[organization_id] = PostRole(role=role, has_divisions=has_divisions)
    return post_roles


def with_post_role(derived: DerivedRoles, post_role: PostRole | None, taxonomy: Taxonomy) -> DerivedRoles:
    """Labels naming only roles elected by members ("Vice Mayor") put the membership on the
    organization's post role: at the division they name, else at large when its posts have
    none. A post role with divisions and no division named keeps today's post."""
    if post_role is None or not names_only_elected_by_members_roles(derived, taxonomy):
        return derived
    if has_division(derived) or not post_role.has_divisions:
        return derived.model_copy(update={"role": post_role.role})
    return derived


def parse_labels(
    records: Sequence[SourceRecord], jurisdiction_ocdid: str, taxonomy: Taxonomy, post_roles: PostRoles
) -> tuple[PostKey, LabelDetails]:
    """One batch's labels, read once: the post they put their person in, and everything else
    they said. Both answers come out of the same parse, which is why they are one call."""
    organization_id = records[0].organization_id
    derived = derive_roles(_labels(records), jurisdiction_ocdid, taxonomy)
    parsed = with_post_role(derived, post_roles.get(organization_id), taxonomy)
    ids_by_label = taxonomy.role_ids
    winner_id = ids_by_label.get(parsed.role) if parsed.role else None

    post = PostKey(
        organization_id=organization_id,
        role_id=winner_id or UNMATCHED_ROLE_ID,
        division_ocdid=parsed.division_ocdid,
    )
    designations = tuple(parsed.other_designations)
    unmatched_text = tuple(
        dict.fromkeys(
            term
            for part in parsed.parts
            if not part.parsed.role
            for term in part.parsed.unmatched
        )
    )
    extra_role_labels = [
        label
        for label in parsed.roles
        if label in ids_by_label and ids_by_label[label] != winner_id
    ]
    details = LabelDetails(
        designations=designations,
        unmatched_text=unmatched_text,
        extra_roles=tuple(ids_by_label[label] for label in extra_role_labels),
        derived_membership_label=render(
            MembershipLabel(
                designations=list(designations),
                demoted_roles=extra_role_labels,
                meta_unmatched_text=list(unmatched_text),
            )
        )
        or None,
    )
    return post, details


def _labels(records: Sequence[SourceRecord]) -> list[str]:
    return list(dict.fromkeys(record.label for record in sorted(records, key=latest_first)))


def _batches_by_person(records: Sequence[SourceRecord]) -> dict[tuple[str, str], list[SourceRecord]]:
    """Each person's records in each organization, from the newest read that labelled them:
    the labels an organization's post role is read from."""
    newest: dict[tuple[str, str], str] = {}
    for record in sorted(records, key=latest_first):
        if record.label:
            newest[(record.organization_id, record.person_id)] = record.changeset_id
    batches: dict[tuple[str, str], list[SourceRecord]] = defaultdict(list)
    for record in records:
        key = (record.organization_id, record.person_id)
        if newest.get(key) == record.changeset_id and record.label:
            batches[key].append(record)
    return batches


def post_keys(
    records: Sequence[SourceRecord], jurisdiction_ocdid: str, taxonomy: Taxonomy
) -> tuple[PostKey, ...]:
    """Distinct posts the records derive, batched per person as `records_by_post` does, sorted
    by `post_id` so rebuilds agree (R6). The organizations' post roles come from the same records."""
    post_roles = organization_post_roles(records, jurisdiction_ocdid, taxonomy)
    batches: dict[tuple[str, str, str], list[SourceRecord]] = {}
    for record in sorted(records, key=latest_first):
        batches.setdefault(
            (record.changeset_id, record.organization_id, record.person_id), []
        ).append(record)

    by_post_id: dict[str, PostKey] = {}
    for batch in batches.values():
        key, _ = parse_labels(batch, jurisdiction_ocdid, taxonomy, post_roles)
        by_post_id[key.post_id] = key

    return tuple(sorted(by_post_id.values(), key=lambda post: post.post_id))


def records_by_post(
    records: Sequence[SourceRecord], jurisdiction_ocdid: str, taxonomy: Taxonomy, post_roles: PostRoles
) -> dict[PostKey, MembershipRecords]:
    """One cluster's live records, bucketed by the post each one landed in, each bucket
    carrying the parse of the newest read that put them there.

    Parsing is per `(changeset, organization)`: the batches arrive oldest first, so the last
    one to land in a post is the one whose labels describe it. A designation the page stopped
    printing goes with the read that stopped printing it.
    """

    batches: dict[tuple[str, str], list[SourceRecord]] = {}
    for record in sorted(records, key=latest_first):
        bucket = (record.changeset_id, record.organization_id)
        batches.setdefault(bucket, []).append(record)

    by_post: dict[PostKey, MembershipRecords] = {}
    for batch in batches.values():
        post, details = parse_labels(batch, jurisdiction_ocdid, taxonomy, post_roles)
        earlier_records = by_post[post].records if post in by_post else ()
        by_post[post] = MembershipRecords(
            records=(*earlier_records, *batch), details=details
        )
    return by_post
