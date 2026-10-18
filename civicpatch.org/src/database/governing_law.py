from pydantic import BaseModel

from database.database import get_pool
from shared.schemas import GoverningLaw


class GoverningLawRow(BaseModel):
    """One active jurisdiction, with what it has: None until a collector run has written it."""

    jurisdiction_ocdid: str
    name: str
    governing_law: GoverningLaw | None


async def get_governing_law_row(jurisdiction_ocdid: str) -> GoverningLawRow | None:
    """None for an unknown or inactive jurisdiction."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT jurisdiction_ocdid, data->>'name', extras_governing_law
            FROM jurisdictions
            WHERE jurisdiction_ocdid = %s AND status = 'active'
            """,
            (jurisdiction_ocdid,),
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return GoverningLawRow(
        jurisdiction_ocdid=row[0],
        name=row[1] or "",
        governing_law=GoverningLaw.model_validate(row[2]) if row[2] is not None else None,
    )


async def save_governing_law(cur, jurisdiction_ocdid: str, governing_law: GoverningLaw) -> None:
    await cur.execute(
        "UPDATE jurisdictions SET extras_governing_law = %s::jsonb WHERE jurisdiction_ocdid = %s",
        (governing_law.model_dump_json(), jurisdiction_ocdid),
    )
