"""A jurisdiction's `extras_organizations`: always replacing the last answer, and only with roles
the config knows. Plan 2 fills it through the organizations collector."""

import database.extras_organizations as extras_organizations_db
from database.activity import record_change
from database.database import get_pool
from database.extras_organizations import ExtrasOrganizationsRow
from database.roles import get_roles
from schemas.activity import Change, FieldChange
from schemas.claims import EntityType
from shared.schemas import GoverningLawOrganizations
from shared.utils.statuses import ActivityType

FIELD = "extras_organizations"


class UnknownJurisdiction(Exception):
    pass


class UnknownRole(Exception):
    """A post names a role the config lacks: such an office reaches config as a proposal from the
    run's issues, never through this column."""


async def set_extras_organizations(
    jurisdiction_ocdid: str, organizations: GoverningLawOrganizations, user_id: str | None
) -> None:
    """`user_id` is None for the service key."""
    row = await extras_organizations_db.get_extras_organizations_row(jurisdiction_ocdid)
    if row is None:
        raise UnknownJurisdiction(jurisdiction_ocdid)
    unknown = _unknown_roles(organizations, {role.id for role in await get_roles()})
    if unknown:
        raise UnknownRole(", ".join(unknown))
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await extras_organizations_db.save_extras_organizations(cur, jurisdiction_ocdid, organizations)
        await _record(cur, row, organizations, user_id)


async def get_extras_organizations(jurisdiction_ocdid: str) -> GoverningLawOrganizations | None:
    row = await extras_organizations_db.get_extras_organizations_row(jurisdiction_ocdid)
    return row.extras_organizations if row else None


def _unknown_roles(organizations: GoverningLawOrganizations, role_ids: set[str]) -> list[str]:
    return sorted({post.role for post in organizations.posts if post.role not in role_ids})


async def _record(
    cur, row: ExtrasOrganizationsRow, organizations: GoverningLawOrganizations, user_id: str | None
) -> None:
    before = row.extras_organizations.model_dump(mode="json") if row.extras_organizations else None
    await record_change(
        cur,
        ActivityType.EDIT_JURISDICTION,
        user_id,
        row.jurisdiction_ocdid,
        Change(
            entity_type=EntityType.JURISDICTION,
            entity_id=row.jurisdiction_ocdid,
            subject=row.name,
            fields=[FieldChange(field=FIELD, before=before, after=organizations.model_dump(mode="json"))],
        ),
    )
