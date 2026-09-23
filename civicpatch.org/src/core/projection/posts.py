"""Which post a person's records in one organization point at.

A post is `(organization, role, division)`.
"""

from collections.abc import Sequence

from shared.schemas import Role
from shared.utils.taxonomy import UNMATCHED_ROLE_ID, Taxonomy

from core.people_roles import derive_roles
from core.projection.facts import PostKey, SourceRecord, latest_first


def post_of(
    records: Sequence[SourceRecord],
    jurisdiction_ocdid: str,
    taxonomy: Taxonomy,
    roles: Sequence[Role],
) -> PostKey:
    """The post these records put their person in."""

    labels = list(
        dict.fromkeys(record.label for record in sorted(records, key=latest_first))
    )

    parsed = derive_roles(labels, jurisdiction_ocdid, taxonomy)

    ids_by_label = {role.label: role.id for role in roles}
    role_id = (
        ids_by_label.get(parsed.role) if parsed.role else None
    ) or UNMATCHED_ROLE_ID

    return PostKey(
        organization_id=records[0].organization_id,
        role_id=role_id,
        division_ocdid=parsed.division_ocdid,
    )


def post_keys(
    records: Sequence[SourceRecord],
    jurisdiction_ocdid: str,
    taxonomy: Taxonomy,
    roles: Sequence[Role],
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
        key = post_of(batch, jurisdiction_ocdid, taxonomy, roles)
        by_post_id[key.post_id] = key

    return tuple(sorted(by_post_id.values(), key=lambda post: post.post_id))


def records_by_post(
    records: Sequence[SourceRecord],
    jurisdiction_ocdid: str,
    taxonomy: Taxonomy,
    roles: Sequence[Role],
) -> dict[PostKey, list[SourceRecord]]:
    """One cluster's live records, bucketed by the post each one landed in.

    Parsing is per `(changeset, organization)`.
    """

    batches: dict[tuple[str, str], list[SourceRecord]] = {}
    for record in sorted(records, key=latest_first):
        bucket = (record.changeset_id, record.organization_id)
        batches.setdefault(bucket, []).append(record)

    by_post: dict[PostKey, list[SourceRecord]] = {}
    for batch in batches.values():
        post = post_of(batch, jurisdiction_ocdid, taxonomy, roles)
        by_post.setdefault(post, []).extend(batch)
    return by_post
