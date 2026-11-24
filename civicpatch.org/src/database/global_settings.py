"""The one monthly cap over every pipeline in every state: a single seeded row."""

from decimal import Decimal

from database.database import get_pool
from psycopg.rows import dict_row
from schemas.pipeline_settings import GlobalSettings


async def get_global_settings() -> GlobalSettings:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute("SELECT monthly_cap_usd, updated_by_user_id::text, updated_at FROM global_settings WHERE id = 1")
        row = await cur.fetchone()
    # The migration seeds the row, so this is belt-and-braces rather than a real branch.
    return GlobalSettings(**row) if row else GlobalSettings()


async def set_global_cap(monthly_cap_usd: Decimal | None, user_id: str | None) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE global_settings SET monthly_cap_usd = %s, updated_by_user_id = %s, updated_at = now() WHERE id = 1",
            (monthly_cap_usd, user_id),
        )
        await conn.commit()
