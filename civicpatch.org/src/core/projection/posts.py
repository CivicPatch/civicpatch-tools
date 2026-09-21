"""Which post a person's records in one organization point at.

A post is `(organization, role, division)`.
"""

import uuid
from collections.abc import Sequence

from pydantic import BaseModel
from shared.schemas import Role
from shared.utils.taxonomy import UNMATCHED_ROLE_ID, Taxonomy

from core.people_roles import derive_roles
from core.projection.facts import SourceRecord, latest_first

POST_NAMESPACE = uuid.UUID("c8374c67-da4d-4aac-a0d9-4f353c803eca")


class PostKey(BaseModel, frozen=True):
    organization_id: str
    role_id: str
    division_ocdid: str

    @property
    def post_id(self) -> str:
        return str(
            uuid.uuid5(
                POST_NAMESPACE,
                f"{self.organization_id}|{self.role_id}|{self.division_ocdid}",
            )
        )


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


def records_by_post(
    records: Sequence[SourceRecord],
    jurisdiction_ocdid: str,
    taxonomy: Taxonomy,
    roles: Sequence[Role],
) -> dict[str, list[SourceRecord]]:
    """One cluster's live records, bucketed by the post each one landed in.

    Parsing is per `(changeset, organization)`.
    """

    batches: dict[tuple[str, str], list[SourceRecord]] = {}
    for record in sorted(records, key=latest_first):
        bucket = (record.changeset_id, record.organization_id)
        batches.setdefault(bucket, []).append(record)

    by_post: dict[str, list[SourceRecord]] = {}
    for batch in batches.values():
        post_id = post_of(batch, jurisdiction_ocdid, taxonomy, roles).post_id
        by_post.setdefault(post_id, []).extend(batch)
    return by_post
