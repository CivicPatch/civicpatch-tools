"""Which organization a scraped record belongs in: the model's pick, else the organization whose
form lists its post role, else the one of those the person already sits in, else the default."""

from pydantic import BaseModel

from shared.utils.taxonomy import MEMBER_ROLE_ID, Taxonomy, lookup_key

from core.people_roles import derive_roles, holds_a_member_post


class PlaceableOrganization(BaseModel):
    id: str
    # The roles its government form lists; empty for an organization the form does not name.
    role_ids: list[str]


def role_ids_of(role_labels: list[str], taxonomy: Taxonomy) -> list[str]:
    ids = []
    for label in role_labels:
        canonical = taxonomy.role_aliases.get(lookup_key(label))
        if canonical is not None:
            ids.append(taxonomy.role_ids[canonical])
    return ids


class LabelRoles(BaseModel):
    # The fold's post role: `member` when a member holds it ("Chair"); None for no role at all.
    post_role_id: str | None
    # Every role the label names ("Cemetery Commissioner, Chair": both).
    named_role_ids: list[str]


def label_roles(label: str, jurisdiction_ocdid: str, taxonomy: Taxonomy) -> LabelRoles:
    derived = derive_roles([label], jurisdiction_ocdid, taxonomy)
    if holds_a_member_post(derived, taxonomy):
        post_role_id = MEMBER_ROLE_ID
    else:
        post_role_id = taxonomy.role_ids.get(derived.role) if derived.role else None
    return LabelRoles(
        post_role_id=post_role_id,
        named_role_ids=[taxonomy.role_ids[role] for role in derived.roles if role in taxonomy.role_ids],
    )


def placed_organization_id(
    label: str,
    picked_organization_id: str | None,
    organizations: list[PlaceableOrganization],
    default_organization_id: str,
    held_organization_ids: set[str],
    jurisdiction_ocdid: str,
    taxonomy: Taxonomy,
) -> str:
    """`held_organization_ids`: where the person already holds a post. A member post never goes by
    the form alone: every board lists members, and "none" from the model means no listed board."""
    if picked_organization_id:
        return picked_organization_id
    roles = label_roles(label, jurisdiction_ocdid, taxonomy)
    if roles.post_role_id is None:
        return default_organization_id
    listing = [organization.id for organization in organizations if roles.post_role_id in organization.role_ids]
    if len(listing) == 1 and roles.post_role_id != MEMBER_ROLE_ID:
        return listing[0]
    named = [
        organization.id
        for organization in organizations
        if any(role_id in organization.role_ids for role_id in roles.named_role_ids)
    ]
    held = [organization_id for organization_id in named if organization_id in held_organization_ids]
    if len(held) == 1:
        return held[0]
    return default_organization_id


def placed_records(
    records_by_person: dict[str, list[dict]],
    organizations: list[PlaceableOrganization],
    default_organization_id: str,
    held_by_person: dict[str, set[str]],
    jurisdiction_ocdid: str,
    taxonomy: Taxonomy,
) -> dict[str, list[dict]]:
    return {
        person_id: [
            {
                **record,
                "organization_id": placed_organization_id(
                    record["label"],
                    record.get("organization_id"),
                    organizations,
                    default_organization_id,
                    held_by_person.get(person_id, set()),
                    jurisdiction_ocdid,
                    taxonomy,
                ),
            }
            for record in records
        ]
        for person_id, records in records_by_person.items()
    }
