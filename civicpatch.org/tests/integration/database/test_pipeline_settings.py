"""Every pipeline's settings per state, on real Postgres: an unconfigured pair reads as the defaults,
the two write paths cannot clobber each other, and pipelines in one state are kept apart.

Isolation: sentinel state 'zw'.
"""

import datetime
import uuid
from decimal import Decimal

import pytest
import pytest_asyncio

from core.spend_limits import Cap
from database.database import get_pool
from database.global_settings import get_global_settings, set_global_cap
from database.pipeline_runs import get_pipeline_run, register_run
from database.pipeline_settings import get_all_pipeline_settings, get_pipeline_settings, set_caps, set_cadence
from services.pipeline_settings import get_pipeline_panel
from services.spend_budget import cap_reached_for
from shared.utils.statuses import PipelineRunKind

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_STATE = "zw"
_SCRAPE = PipelineRunKind.PEOPLE_COLLECTOR
_LAW = PipelineRunKind.GOVERNING_LAW_COLLECTOR


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM pipeline_settings WHERE state = %s", (_STATE,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def _clean():
    await _wipe()
    yield
    await _wipe()


async def test_an_unconfigured_pipeline_reads_as_the_defaults():
    settings = await get_pipeline_settings(_STATE, _LAW)

    assert (settings.cadence_days, settings.pipeline_run_cap_usd, settings.monthly_cap_usd) == (None, None, None)


async def test_setting_the_cadence_keeps_the_caps_and_the_reverse():
    await set_caps(_STATE, _LAW, Decimal("0.25"), Decimal("5"), None)
    await set_cadence(_STATE, _LAW, 365, None, None)
    await set_caps(_STATE, _LAW, Decimal("0.30"), Decimal("6"), None)

    settings = await get_pipeline_settings(_STATE, _LAW)
    assert (settings.cadence_days, settings.pipeline_run_cap_usd, settings.monthly_cap_usd) == (
        365,
        Decimal("0.3000"),
        Decimal("6.0000"),
    )


async def test_pipelines_in_one_state_are_kept_apart():
    await set_cadence(_STATE, _SCRAPE, 30, None, None)
    await set_cadence(_STATE, _LAW, 365, None, None)

    ours = [(s.kind, s.cadence_days) for s in await get_all_pipeline_settings() if s.state == _STATE]
    assert ours == [(_LAW, 365), (_SCRAPE, 30)]


async def test_zero_is_a_cap_and_none_is_not_the_same_as_it():
    """`$0` means spend nothing, which None cannot say: None means the default, or no monthly cap."""
    await set_caps(_STATE, _LAW, Decimal("0"), None, None)

    settings = await get_pipeline_settings(_STATE, _LAW)
    assert (settings.pipeline_run_cap_usd, settings.monthly_cap_usd) == (Decimal("0"), None)


async def test_a_cadence_of_zero_days_is_refused():
    """It would schedule a pass that starts the instant the last one ended, forever."""
    with pytest.raises(Exception) as excinfo:
        await set_cadence(_STATE, _LAW, 0, None, None)

    assert "pipeline_settings_cadence_days_positive" in str(excinfo.value)


async def test_a_negative_cap_is_refused():
    with pytest.raises(Exception) as excinfo:
        await set_caps(_STATE, _LAW, Decimal("-1"), None, None)

    assert "pipeline_settings_caps_not_negative" in str(excinfo.value)


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


async def test_a_run_records_the_cap_its_state_was_set_to():
    """Resolved in the INSERT, so neither dispatch path can forget to look it up — and recorded,
    so `why did this run stop at $0.05` is answerable from the row rather than from a log."""
    await set_caps(_STATE, PipelineRunKind.PEOPLE_COLLECTOR, Decimal("0.05"), None, None)
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
        await register_run(run_id, PipelineRunKind.PEOPLE_COLLECTOR, ocdid, {})

        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT pipeline_run_cap_usd FROM pipeline_runs WHERE id = %s", (run_id,)
            )
            row = await cur.fetchone()
        assert row is not None and row[0] == Decimal("0.0500")

        # What the scraper's config endpoint reads. It returned no cap at all, so every run
        # inherited the pipeline's default whatever the state was set to.
        run = await get_pipeline_run(run_id)
        assert run is not None
        assert run["pipeline_run_cap_usd"] == Decimal("0.0500")
        assert run["jurisdiction_ocdid"] == ocdid
    finally:
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute("DELETE FROM pipeline_runs WHERE id = %s", (run_id,))
            await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (ocdid,))
            await conn.commit()


async def test_a_run_in_an_unconfigured_state_inherits_rather_than_failing():
    """No state row, no jurisdiction row, and a state that set no cap all yield NULL, which the
    pipeline reads as `use pipeline.yml`. The subquery matching nothing is the common case."""
    run_id = str(uuid.uuid4())
    try:
        await register_run(run_id, PipelineRunKind.PEOPLE_COLLECTOR, "ocd-jurisdiction/country:us/state:zw/place:nope/government", {})

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


async def test_the_budget_gate_reads_caps_and_spend_together():
    """The service half: two reads and the pure decision, against real rows. A state with no
    caps set is never over budget, however much it has spent."""
    assert await cap_reached_for(_STATE, PipelineRunKind.PEOPLE_COLLECTOR) is None

    await set_caps(_STATE, PipelineRunKind.PEOPLE_COLLECTOR, None, Decimal("0"), None)
    # A monthly cap of $0 is reached before anything is spent — the stop switch.
    assert await cap_reached_for(_STATE, PipelineRunKind.PEOPLE_COLLECTOR) == Cap.STATE_MONTH


async def test_the_settings_panel_answers_from_one_moment():
    """Five reads and one piece of arithmetic, assembled in a service rather than a router.
    A state nobody has configured still answers — every field has a meaning at NULL."""
    panel = await get_pipeline_panel(_STATE, PipelineRunKind.PEOPLE_COLLECTOR)

    assert panel.state == _STATE
    assert panel.cadence_days is None
    assert panel.next_run_at is None  # manual has no next run
    assert panel.spent_this_month_usd == Decimal("0")
    assert panel.cap_reached is None
    assert panel.cost_per_run_this_month_usd is None
    assert panel.cost_cap_hits_this_month == 0


async def test_a_cadence_gives_the_panel_a_next_run():
    await set_cadence(_STATE, PipelineRunKind.PEOPLE_COLLECTOR, 30, datetime.date(2026, 9, 1), None)

    panel = await get_pipeline_panel(_STATE, PipelineRunKind.PEOPLE_COLLECTOR)

    assert panel.cadence_days == 30
    assert panel.next_run_at is not None
