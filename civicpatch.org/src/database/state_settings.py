"""Cadence and budget, read and written.

`state_settings` has no row for a state until someone configures one, and that absence is not a
missing value — it is the default: manual cadence, inherited per-run cap, no monthly ceiling. So
every read here answers for every state, configured or not, and no caller has to handle `None`
differently from a row of all-NULLs.
"""

from decimal import Decimal

from database.database import get_pool
from psycopg.rows import dict_row
from schemas.state_settings import GlobalSettings, StateSettings

_COLUMNS = (
    "state, cadence_days, cadence_start, pipeline_run_cap_usd, monthly_cap_usd, "
    "updated_by_user_id::text, updated_at"
)


async def get_state_settings(state: str) -> StateSettings:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            f"SELECT {_COLUMNS} FROM state_settings WHERE state = %s", (state,)
        )
        row = await cur.fetchone()
    # An unconfigured state is not an error and not an empty result — it is the defaults.
    return StateSettings(**row) if row else StateSettings(state=state)


async def get_all_state_settings() -> dict[str, StateSettings]:
    """Only the configured states. Callers wanting every state join this onto their own list —
    which is what keeps this from having to know what the states are."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(f"SELECT {_COLUMNS} FROM state_settings ORDER BY state")
        rows = await cur.fetchall()
    return {row["state"]: StateSettings(**row) for row in rows}


async def set_cadence(
    state: str, cadence_days: int | None, cadence_start, user_id: str | None
) -> None:
    """Maintainer-writable: how often a state is scraped. Separate from the caps below because
    admins allocate and maintainers spend — see the permissions table in README."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO state_settings (state, cadence_days, cadence_start, updated_by_user_id)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (state) DO UPDATE
               SET cadence_days = EXCLUDED.cadence_days,
                   cadence_start = EXCLUDED.cadence_start,
                   updated_by_user_id = EXCLUDED.updated_by_user_id,
                   updated_at = now()
            """,
            (state, cadence_days, cadence_start, user_id),
        )
        await conn.commit()


async def set_caps(
    state: str,
    pipeline_run_cap_usd: Decimal | None,
    monthly_cap_usd: Decimal | None,
    user_id: str | None,
) -> None:
    """Admin-writable: how much money exists. Kept apart from the cadence so that setting one
    cannot silently clear the other — an UPSERT of the whole row would."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO state_settings
                (state, pipeline_run_cap_usd, monthly_cap_usd, updated_by_user_id)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (state) DO UPDATE
               SET pipeline_run_cap_usd = EXCLUDED.pipeline_run_cap_usd,
                   monthly_cap_usd = EXCLUDED.monthly_cap_usd,
                   updated_by_user_id = EXCLUDED.updated_by_user_id,
                   updated_at = now()
            """,
            (state, pipeline_run_cap_usd, monthly_cap_usd, user_id),
        )
        await conn.commit()


async def get_global_settings() -> GlobalSettings:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT monthly_cap_usd, updated_by_user_id::text, updated_at "
            "FROM global_settings WHERE id = 1"
        )
        row = await cur.fetchone()
    # The migration seeds the row, so this is belt-and-braces rather than a real branch.
    return GlobalSettings(**row) if row else GlobalSettings()


async def set_global_cap(monthly_cap_usd: Decimal | None, user_id: str | None) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE global_settings
               SET monthly_cap_usd = %s, updated_by_user_id = %s, updated_at = now()
             WHERE id = 1
            """,
            (monthly_cap_usd, user_id),
        )
        await conn.commit()
