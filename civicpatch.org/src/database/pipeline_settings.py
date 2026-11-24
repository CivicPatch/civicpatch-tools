"""Every pipeline's cadence and caps, per state, read and written. A state and pipeline with no row is
the defaults, so every read answers for any pair, configured or not."""

from datetime import date
from decimal import Decimal

from database.database import get_pool
from psycopg.rows import dict_row
from schemas.pipeline_settings import PipelineSettings
from shared.utils.statuses import PipelineRunKind

_COLUMNS = (
    "state, kind, cadence_days, cadence_anchor, pipeline_run_cap_usd, monthly_cap_usd, "
    "updated_by_user_id::text, updated_at"
)


async def get_pipeline_settings(state: str, kind: PipelineRunKind) -> PipelineSettings:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(f"SELECT {_COLUMNS} FROM pipeline_settings WHERE state = %s AND kind = %s", (state, kind))
        row = await cur.fetchone()
    return PipelineSettings(**row) if row else PipelineSettings(state=state, kind=kind)


async def get_all_pipeline_settings() -> list[PipelineSettings]:
    """Only the configured pairs; callers wanting every state join this onto their own list."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(f"SELECT {_COLUMNS} FROM pipeline_settings ORDER BY state, kind")
        rows = await cur.fetchall()
    return [PipelineSettings(**row) for row in rows]


async def set_cadence(
    state: str, kind: PipelineRunKind, cadence_days: int | None, cadence_anchor: date | None, user_id: str | None
) -> None:
    """Apart from the caps, so setting one cannot clear the other, as an upsert of the whole row would."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO pipeline_settings (state, kind, cadence_days, cadence_anchor, updated_by_user_id)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (state, kind) DO UPDATE
               SET cadence_days = EXCLUDED.cadence_days,
                   cadence_anchor = EXCLUDED.cadence_anchor,
                   updated_by_user_id = EXCLUDED.updated_by_user_id,
                   updated_at = now()
            """,
            (state, kind, cadence_days, cadence_anchor, user_id),
        )
        await conn.commit()


async def set_caps(
    state: str,
    kind: PipelineRunKind,
    pipeline_run_cap_usd: Decimal | None,
    monthly_cap_usd: Decimal | None,
    user_id: str | None,
) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO pipeline_settings (state, kind, pipeline_run_cap_usd, monthly_cap_usd, updated_by_user_id)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (state, kind) DO UPDATE
               SET pipeline_run_cap_usd = EXCLUDED.pipeline_run_cap_usd,
                   monthly_cap_usd = EXCLUDED.monthly_cap_usd,
                   updated_by_user_id = EXCLUDED.updated_by_user_id,
                   updated_at = now()
            """,
            (state, kind, pipeline_run_cap_usd, monthly_cap_usd, user_id),
        )
        await conn.commit()


async def sum_monthly_caps() -> Decimal:
    """Shown, never enforced: it may exceed the global cap, since the caps are ceilings, not reservations."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT COALESCE(sum(monthly_cap_usd), 0) FROM pipeline_settings")
        row = await cur.fetchone()
    assert row, "sum() always returns a row"
    return row[0]
