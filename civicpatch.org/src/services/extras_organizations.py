"""A jurisdiction's `extras_organizations`: always replacing the last answer, and only with roles
the config knows. Plan 2 fills it through the organizations collector."""

import database.extras_organizations as extras_organizations_db
from database.activity import record_change
from database.database import get_pool
from database.extras_organizations import ExtrasOrganizationsRow
from database.jurisdiction_configs import get_jurisdiction_configs
from database.roles import get_roles
from pydantic import BaseModel
from schemas.activity import Change, FieldChange
from schemas.claims import EntityType
from shared.schemas import GoverningLaw, GovernmentForm, GoverningLawOrganizations
from shared.utils.id_utils import parse_jurisdiction_ocdid
from shared.utils.layered_config import MergedConfig, jurisdiction_config
from shared.utils.statuses import ActivityType

FIELD = "extras_organizations"


class UnknownJurisdiction(Exception):
    pass


class CollectorConfig(BaseModel):
    """What an organizations_collector run is told when it starts."""

    name: str
    governing_law: GoverningLaw | None
    jurisdiction_config: MergedConfig
    government_form: GovernmentForm | None


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


async def collector_config(jurisdiction_ocdid: str) -> CollectorConfig:
    """The jurisdiction's name, its extras_governing_law, its merged config, and its
    government form. The caller adds the run's cap."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT data->>'name', extras_governing_law, extras_government_form
            FROM jurisdictions
            WHERE jurisdiction_ocdid = %s AND status = 'active'
            """,
            (jurisdiction_ocdid,),
        )
        row = await cur.fetchone()
    if row is None:
        raise UnknownJurisdiction(jurisdiction_ocdid)
    name = row[0] or ""
    governing_law = GoverningLaw.model_validate(row[1]) if row[1] is not None else None
    government_form = GovernmentForm(row[2]) if row[2] else None
    parsed = parse_jurisdiction_ocdid(jurisdiction_ocdid)
    configs = await get_jurisdiction_configs()
    jury_config = jurisdiction_config(configs, parsed.state, parsed.level)
    return CollectorConfig(name=name, governing_law=governing_law, jurisdiction_config=jury_config, government_form=government_form)


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
