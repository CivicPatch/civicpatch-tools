"""Which post a person's records in one organization point at, and what else those labels
said while we were reading them.

A post is `(organization, role, division)`. One read of the labels answers both questions, so
`parse_labels` is the only place `derive_roles` runs for a membership.
"""

from collections.abc import Sequence

from shared.utils.taxonomy import UNMATCHED_ROLE_ID, Taxonomy

from core.membership_label import MembershipLabel, render
from core.people_roles import derive_roles
from core.projection.facts import PostKey, SourceRecord, latest_first
from core.projection.membership_details import LabelDetails, MembershipRecords


def parse_labels(
    records: Sequence[SourceRecord], jurisdiction_ocdid: str, taxonomy: Taxonomy
) -> tuple[PostKey, LabelDetails]:
    """One batch's labels, read once: the post they put their person in, and everything else
    they said. Both answers come out of the same parse, which is why they are one call."""
    labels = list(
        dict.fromkeys(record.label for record in sorted(records, key=latest_first))
    )
    parsed = derive_roles(labels, jurisdiction_ocdid, taxonomy)
    ids_by_label = taxonomy.role_ids
    winner_id = ids_by_label.get(parsed.role) if parsed.role else None

    post = PostKey(
        organization_id=records[0].organization_id,
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


def post_keys(
    records: Sequence[SourceRecord], jurisdiction_ocdid: str, taxonomy: Taxonomy
) -> tuple[PostKey, ...]:
    """Distinct posts the records derive, batched per person as `records_by_post` does, sorted
    by `post_id` so rebuilds agree (R6)."""
    batches: dict[tuple[str, str, str], list[SourceRecord]] = {}
    for record in sorted(records, key=latest_first):
        batches.setdefault(
            (record.changeset_id, record.organization_id, record.person_id), []
        ).append(record)

    by_post_id: dict[str, PostKey] = {}
    for batch in batches.values():
        key, _ = parse_labels(batch, jurisdiction_ocdid, taxonomy)
        by_post_id[key.post_id] = key

    return tuple(sorted(by_post_id.values(), key=lambda post: post.post_id))


def records_by_post(
    records: Sequence[SourceRecord], jurisdiction_ocdid: str, taxonomy: Taxonomy
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
        post, details = parse_labels(batch, jurisdiction_ocdid, taxonomy)
        earlier_records = by_post[post].records if post in by_post else ()
        by_post[post] = MembershipRecords(
            records=(*earlier_records, *batch), details=details
        )
    return by_post
