"""Which organization a scraped record belongs in: the one whose form lists its post role, else
the one the model picked, else the default."""

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


def post_role_id(label: str, jurisdiction_ocdid: str, taxonomy: Taxonomy) -> str | None:
    """The fold's answer for one label: `member` when a member holds it ("Chair")."""
    derived = derive_roles([label], jurisdiction_ocdid, taxonomy)
    if holds_a_member_post(derived, taxonomy):
        return MEMBER_ROLE_ID
    return taxonomy.role_ids.get(derived.role) if derived.role else None


def placed_organization_id(
    label: str,
    picked_organization_id: str | None,
    organizations: list[PlaceableOrganization],
    default_organization_id: str,
    jurisdiction_ocdid: str,
    taxonomy: Taxonomy,
) -> str:
    role_id = post_role_id(label, jurisdiction_ocdid, taxonomy)
    if role_id is not None and role_id != MEMBER_ROLE_ID:
        listing = [organization.id for organization in organizations if role_id in organization.role_ids]
        if len(listing) == 1:
            return listing[0]
    return picked_organization_id or default_organization_id


def placed_rows(
    rows: list[dict],
    organizations: list[PlaceableOrganization],
    default_organization_id: str,
    jurisdiction_ocdid: str,
    taxonomy: Taxonomy,
) -> list[dict]:
    return [
        {
            **row,
            "organization_id": placed_organization_id(
                row["label"],
                row.get("organization_id"),
                organizations,
                default_organization_id,
                jurisdiction_ocdid,
                taxonomy,
            ),
        }
        for row in rows
    ]
