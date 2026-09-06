"""Integration tests for cadence and budget settings.

Real Postgres: the point of this module is that an *unconfigured* state reads as the defaults
rather than as an absent row, and that the two write paths cannot clobber each other. Both are
properties of the SQL — an UPSERT of the whole row would break the second, silently.

Isolation: sentinel state 'zw'. `global_settings` is a single global row, so its test restores
whatever it found rather than assuming a value.
"""

from decimal import Decimal
import datetime
import uuid

import pytest
import pytest_asyncio

from core.spend_limits import Cap
from database.database import get_pool
from database.pipeline_runs import register_run
from services.spend_budget import cap_reached_for_state
from database.state_settings import (
    get_all_state_settings,
    get_global_settings,
    get_state_settings,
    set_caps,
    set_cadence,
    set_global_cap,
)

_STATE = "zw"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM state_settings WHERE state = %s", (_STATE,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def _clean():
    await _wipe()
    yield
    await _wipe()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_state_nobody_configured_reads_as_the_defaults():
    """No row is not a missing value — it is manual cadence, inherited per-run cap, no monthly
    cap. If this returned None, fifty rows would have to be seeded to avoid it."""
    settings = await get_state_settings(_STATE)

    assert settings.state == _STATE
    assert settings.cadence_days is None
    assert settings.pipeline_run_cap_usd is None
    assert settings.monthly_cap_usd is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_setting_caps_does_not_clear_the_cadence():
    """Admins allocate, maintainers spend — two writers on one row. An UPSERT of the whole row
    would let whichever saved last erase the other's column."""
    await set_cadence(_STATE, 30, datetime.date(2026, 9, 1), None)
    await set_caps(_STATE, Decimal("0.50"), Decimal("12.00"), None)

    settings = await get_state_settings(_STATE)

    assert settings.cadence_days == 30
    assert settings.cadence_start == datetime.date(2026, 9, 1)
    assert settings.pipeline_run_cap_usd == Decimal("0.5000")
    assert settings.monthly_cap_usd == Decimal("12.0000")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_setting_the_cadence_does_not_clear_the_caps():
    await set_caps(_STATE, Decimal("0.50"), Decimal("12.00"), None)
    await set_cadence(_STATE, 14, None, None)

    settings = await get_state_settings(_STATE)

    assert settings.cadence_days == 14
    assert settings.pipeline_run_cap_usd == Decimal("0.5000")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_zero_is_a_setting_and_null_is_not_the_same_as_it():
    """`$0` means spend nothing on this state, which NULL cannot say — NULL means inherit."""
    await set_caps(_STATE, Decimal("0"), None, None)

    settings = await get_state_settings(_STATE)

    assert settings.pipeline_run_cap_usd == Decimal("0")
    assert settings.monthly_cap_usd is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_cadence_of_zero_days_is_refused():
    """It would schedule a pass that starts the instant the last one ended, forever."""
    with pytest.raises(Exception) as excinfo:
        await set_cadence(_STATE, 0, None, None)

    assert "state_settings_cadence_days_positive" in str(excinfo.value)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_negative_cap_is_refused():
    with pytest.raises(Exception) as excinfo:
        await set_caps(_STATE, Decimal("-1"), None, None)

    assert "state_settings_caps_not_negative" in str(excinfo.value)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_only_configured_states_are_listed():
    """The map is joined onto a caller's own list of states, which is what keeps this module
    from needing to know what the states are."""
    assert _STATE not in await get_all_state_settings()

    await set_cadence(_STATE, 30, None, None)

    assert (await get_all_state_settings())[_STATE].cadence_days == 30


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_global_row_exists_without_anyone_creating_it():
    """Seeded by the migration, so every reader is a plain SELECT rather than one that has to
    cope with no row."""
    before = await get_global_settings()
    try:
        await set_global_cap(Decimal("40.00"), None)
        assert (await get_global_settings()).monthly_cap_usd == Decimal("40.0000")

        await set_global_cap(None, None)
        assert (await get_global_settings()).monthly_cap_usd is None
    finally:
        await set_global_cap(before.monthly_cap_usd, before.updated_by_user_id)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_run_records_the_cap_its_state_was_set_to():
    """Resolved in the INSERT, so neither dispatch path can forget to look it up — and recorded,
    so `why did this run stop at $0.05` is answerable from the row rather than from a log."""
    await set_caps(_STATE, Decimal("0.05"), None, None)
    ocdid = f"ocd-jurisdiction/country:us/state:{_STATE}/place:zw_one/government"
    run_id = str(uuid.uuid4())

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, data, updated_at) "
            "VALUES (%s, %s, '{}'::jsonb, now()) ON CONFLICT DO NOTHING",
            (ocdid, _STATE),
        )
        await conn.commit()
    try:
        await register_run(run_id, ocdid, {})

        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT pipeline_run_cap_usd FROM pipeline_runs WHERE id = %s", (run_id,)
            )
            row = await cur.fetchone()
        assert row is not None and row[0] == Decimal("0.0500")
    finally:
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute("DELETE FROM pipeline_runs WHERE id = %s", (run_id,))
            await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (ocdid,))
            await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_run_in_an_unconfigured_state_inherits_rather_than_failing():
    """No state row, no jurisdiction row, and a state that set no cap all yield NULL, which the
    pipeline reads as `use pipeline.yml`. The subquery matching nothing is the common case."""
    run_id = str(uuid.uuid4())
    try:
        await register_run(run_id, "ocd-jurisdiction/country:us/state:zw/place:nope/government", {})

        pool = await get_pool()
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT pipeline_run_cap_usd FROM pipeline_runs WHERE id = %s", (run_id,)
            )
            row = await cur.fetchone()
        assert row is not None and row[0] is None
    finally:
        pool = await get_pool()
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute("DELETE FROM pipeline_runs WHERE id = %s", (run_id,))
            await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_budget_gate_reads_caps_and_spend_together():
    """The service half: two reads and the pure decision, against real rows. A state with no
    caps set is never over budget, however much it has spent."""
    assert await cap_reached_for_state(_STATE) is None

    await set_caps(_STATE, None, Decimal("0"), None)
    # A monthly cap of $0 is reached before anything is spent — the stop switch.
    assert await cap_reached_for_state(_STATE) == Cap.STATE_MONTH
