"""`jurisdictions.extras_organizations`: what a jurisdiction's governing law says its government
is made of. Written by the organizations collector; read by the fold and the jurisdiction call."""

from pydantic import BaseModel
from shared.schemas import GoverningLawOrganizations

from database.database import get_pool


class ExtrasOrganizationsRow(BaseModel):
    """One active jurisdiction, with what it has: None until the collector has written it."""

    jurisdiction_ocdid: str
    name: str
    extras_organizations: GoverningLawOrganizations | None


async def get_extras_organizations_row(jurisdiction_ocdid: str) -> ExtrasOrganizationsRow | None:
    """None for an unknown or inactive jurisdiction."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT jurisdiction_ocdid, data->>'name', extras_organizations
            FROM jurisdictions
            WHERE jurisdiction_ocdid = %s AND status = 'active'
            """,
            (jurisdiction_ocdid,),
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return ExtrasOrganizationsRow(jurisdiction_ocdid=row[0], name=row[1] or "", extras_organizations=_parsed(row[2]))


async def get_extras_organizations(cur, jurisdiction_ocdid: str) -> GoverningLawOrganizations | None:
    """Inside a caller's transaction: the fold reads it beside the facts it loads."""
    await cur.execute("SELECT extras_organizations FROM jurisdictions WHERE jurisdiction_ocdid = %s", (jurisdiction_ocdid,))
    row = await cur.fetchone()
    return _parsed(row[0]) if row else None


async def get_extras_organizations_by_input_hash(input_hash: str) -> GoverningLawOrganizations | None:
    """The newest answer, from any active jurisdiction, read from the same inputs."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT extras_organizations
            FROM jurisdictions
            WHERE extras_organizations->'extras'->>'input_hash' = %s AND status = 'active'
            ORDER BY (extras_organizations->'extras'->>'governing_law_collected_at')::timestamptz DESC
            LIMIT 1
            """,
            (input_hash,),
        )
        row = await cur.fetchone()
    return _parsed(row[0]) if row else None


async def save_extras_organizations(cur, jurisdiction_ocdid: str, organizations: GoverningLawOrganizations) -> None:
    await cur.execute(
        "UPDATE jurisdictions SET extras_organizations = %s::jsonb WHERE jurisdiction_ocdid = %s",
        (organizations.model_dump_json(), jurisdiction_ocdid),
    )


def _parsed(value) -> GoverningLawOrganizations | None:
    return GoverningLawOrganizations.model_validate(value) if value is not None else None
