"""What people claim about an organization: the roles it holds in its place, beyond or against
its law and config. No column holds these; they are read back from claims."""

from core.organization_derivation import ROLES_FIELD, ClaimedRoles, OrganizationRole
from database import claims
from schemas.claims import ClaimKind, EntityType


async def claimed_roles(cur, organization_ids: list[str]) -> dict[str, ClaimedRoles]:
    """By organization id, only the claims that currently apply."""
    claimed = await claims.claimed_values(cur, EntityType.ORGANIZATION, organization_ids)
    by_organization = {}
    for organization_id, by_field in claimed.items():
        roles = by_field.get(ROLES_FIELD, {})
        by_organization[organization_id] = ClaimedRoles(
            accepted=[OrganizationRole(**value) for value in roles.get(ClaimKind.ACCEPT, [])],
            rejected=[OrganizationRole(**value) for value in roles.get(ClaimKind.REJECT, [])],
        )
    return by_organization

