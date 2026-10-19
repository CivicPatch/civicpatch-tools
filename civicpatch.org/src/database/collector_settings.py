"""The charter collectors' spend bounds: one seeded row per kind, read and written."""

from decimal import Decimal

from database.database import get_pool
from psycopg.rows import dict_row
from schemas.collector_settings import CollectorSettings
from shared.utils.statuses import PipelineRunKind


async def get_collector_settings(kind: PipelineRunKind) -> CollectorSettings:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT kind, pipeline_run_cap_usd, monthly_cap_usd, updated_by_user_id::text, updated_at "
            "FROM collector_settings WHERE kind = %s",
            (kind,),
        )
        row = await cur.fetchone()
    assert row, "migration 249 seeds a row for every collector kind"
    return CollectorSettings(**row)


async def set_collector_caps(
    kind: PipelineRunKind, pipeline_run_cap_usd: Decimal, monthly_cap_usd: Decimal | None, user_id: str | None
) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE collector_settings
               SET pipeline_run_cap_usd = %s, monthly_cap_usd = %s, updated_by_user_id = %s, updated_at = now()
             WHERE kind = %s
            """,
            (pipeline_run_cap_usd, monthly_cap_usd, user_id, kind),
        )
        await conn.commit()
