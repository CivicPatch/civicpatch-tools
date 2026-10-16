from pydantic import BaseModel

from core.organization_derivation import ExistingOrganization
from database.database import get_pool
from shared.schemas import GovernmentForm

# cp.org's own column, set by a person or a scrape; the open-data sync never writes it.
_INPUTS_SELECT = "SELECT jurisdiction_ocdid, data->>'name', extras_government_form FROM jurisdictions"


class GovernmentFormInputs(BaseModel):
    """One active jurisdiction, with what resolving its government form reads."""

    jurisdiction_ocdid: str
    name: str
    government_form: GovernmentForm | None


def _inputs(row) -> GovernmentFormInputs:
    return GovernmentFormInputs(jurisdiction_ocdid=row[0], name=row[1] or "", government_form=row[2])


async def get_government_form_inputs(jurisdiction_ocdid: str) -> GovernmentFormInputs | None:
    """None for an unknown or inactive jurisdiction."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            _INPUTS_SELECT + " WHERE jurisdiction_ocdid = %s AND status = 'active'",
            (jurisdiction_ocdid,),
        )
        row = await cur.fetchone()
    return _inputs(row) if row else None


async def save_government_form(cur, jurisdiction_ocdid: str, government_form: GovernmentForm) -> None:
    await cur.execute(
        "UPDATE jurisdictions SET extras_government_form = %s WHERE jurisdiction_ocdid = %s",
        (government_form, jurisdiction_ocdid),
    )


async def fill_government_form(cur, jurisdiction_ocdid: str, government_form: GovernmentForm) -> bool:
    """Save it only while none is saved. Returns whether it was."""
    await cur.execute(
        """
        UPDATE jurisdictions SET extras_government_form = %s
        WHERE jurisdiction_ocdid = %s AND extras_government_form IS NULL
        """,
        (government_form, jurisdiction_ocdid),
    )
    return cur.rowcount > 0


async def government_form_inputs_below_state() -> list[GovernmentFormInputs]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(_INPUTS_SELECT + " WHERE status = 'active' AND level <> 'state'")
        return [_inputs(row) for row in await cur.fetchall()]


async def list_organizations(
    jurisdiction_ocdids: list[str],
) -> dict[str, list[ExistingOrganization]]:
    """Each jurisdiction's organizations, the default first."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT jurisdiction_ocdid, id::text, name, meta_is_default
            FROM organizations
            WHERE jurisdiction_ocdid = ANY(%s)
            ORDER BY meta_is_default DESC, sort_order, name
            """,
            (jurisdiction_ocdids,),
        )
        rows = await cur.fetchall()
    by_jurisdiction: dict[str, list[ExistingOrganization]] = {}
    for row in rows:
        by_jurisdiction.setdefault(row[0], []).append(
            ExistingOrganization(id=row[1], name=row[2], meta_is_default=row[3])
        )
    return by_jurisdiction

