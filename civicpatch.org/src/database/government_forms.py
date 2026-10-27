from pydantic import BaseModel

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
