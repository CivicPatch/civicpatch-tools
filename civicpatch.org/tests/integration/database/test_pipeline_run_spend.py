"""Integration tests for per-state collection spend.

Real Postgres: the figure is a three-table join with a per-run distinct count, so nothing here
survives being unit-tested against a mapper. What is worth locking down is the denominator —
spend is averaged over *runs*, not calls, and a run that spent money and then failed is still
a run.

Isolation: sentinel state 'zx', its own state code so another suite's fixtures cannot leak into
the row.
"""

from decimal import Decimal

import pytest
import pytest_asyncio

from database.pipeline_run_spend import (
    get_fleet_month_to_date_cost_per_run,
    get_fleet_month_to_date_seconds_per_run,
    get_month_to_date_cost_per_run,
    get_month_to_date_spend,
)
from database.database import get_pool
from database.llm_calls import record_calls
from tests.integration import factories

_STATE = "zx"
_OCDID = f"ocd-jurisdiction/country:us/state:{_STATE}/place:zx_one/government"
_OCDID_TWO = f"ocd-jurisdiction/country:us/state:{_STATE}/place:zx_two/government"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        for ocdid in (_OCDID, _OCDID_TWO):
            await cur.execute(
                "DELETE FROM llm_calls lc USING pipeline_runs pr "
                "WHERE lc.pipeline_run_id = pr.id AND pr.jurisdiction_ocdid = %s",
                (ocdid,),
            )
            await cur.execute(
                "DELETE FROM source_records WHERE jurisdiction_ocdid = %s", (ocdid,)
            )
            await cur.execute(
                "DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (ocdid,)
            )
            await cur.execute(
                "DELETE FROM pipeline_runs WHERE jurisdiction_ocdid = %s", (ocdid,)
            )
            await cur.execute(
                "DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (ocdid,)
            )
            # register_run() (via factories._register_run) writes a pipeline_run_start row here —
            # left uncleaned, it collides with any other test reading the activity feed for 'zx'.
            await cur.execute(
                "DELETE FROM activity WHERE jurisdiction_ocdid = %s", (ocdid,)
            )


@pytest_asyncio.fixture(autouse=True)
async def _clean():
    await _wipe()
    yield
    await _wipe()


async def _seed_jurisdiction(ocdid: str = _OCDID) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO jurisdictions (jurisdiction_ocdid, state, data, updated_at)
            VALUES (%s, %s, %s::jsonb, now())
            ON CONFLICT (jurisdiction_ocdid) DO NOTHING
            """,
            (ocdid, _STATE, '{"name": "Zx Place"}'),
        )


def _call(cost: str, **overrides) -> dict:
    return {
        "prompt_name": "municipality_officials",
        "source_url": "https://example.gov/council",
        "chunk_index": None,
        "chunk_count": None,
        "attempt": 1,
        "seed": None,
        "gateway": "openrouter",
        "model": "deepseek/deepseek-v4-flash",
        "routed_model": "deepseek/deepseek-v4-flash-20260801",
        "upstream_provider": "AtlasCloud",
        "generation_id": None,
        "input_tokens": 100,
        "output_tokens": 50,
        "cached_input_tokens": 0,
        "reasoning_tokens": 0,
        "cost_usd": cost,
        "web_search": False,
        "duration_ms": 1_000,
        "finish_reason": "stop",
        "error": None,
        **overrides,
    }


async def _backdate(run_id: str, days: int) -> None:
    """The window filters on `llm_calls.created_at`, so ageing a run means ageing its calls."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE llm_calls SET created_at = now() - make_interval(days => %s) "
            "WHERE pipeline_run_id = %s",
            (days, run_id),
        )
        await conn.commit()


# --- Month to date, for the two monthly caps ------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
async def test_month_to_date_reports_this_state_and_everything_together():
    """One statement for both scopes: read separately they can disagree about which month it is
    at a boundary."""
    await _seed_jurisdiction()
    run = await factories.start_run(_OCDID)
    await record_calls(run, [_call("0.04")])

    state_spent, global_spent = await get_month_to_date_spend(_STATE)

    assert state_spent == Decimal("0.04")
    assert global_spent >= state_spent  # other states share the fleet figure


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_run_that_minted_no_changeset_still_counts_against_the_cap():
    """Per run, not per changeset: a scrape that spent money and then failed produced nothing to
    review, and leaving it out would flatter exactly the states that waste the most."""
    await _seed_jurisdiction()
    run = await factories.start_run(_OCDID)
    await record_calls(run, [_call("0.05")])
    await factories.fail_run(run)

    state_spent, _global = await get_month_to_date_spend(_STATE)

    assert state_spent == Decimal("0.05")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_last_month_s_spend_does_not_count_against_this_month():
    """A calendar month, not a rolling window — a rolling one would let spend refused on the
    30th become affordable again on the 31st."""
    await _seed_jurisdiction()
    old = await factories.start_run(_OCDID)
    await record_calls(old, [_call("5.00")])
    await _backdate(old, 45)

    state_spent, _global = await get_month_to_date_spend(_STATE)

    assert state_spent == Decimal("0")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_state_that_spent_nothing_reads_zero_rather_than_null():
    """The one place zero is the honest answer: a budget check needs a number to compare, and
    the caller measures it against a cap rather than displaying it as a cost."""
    state_spent, _global = await get_month_to_date_spend(_STATE)

    assert state_spent == Decimal("0")


# --- Month to date, cost per run ------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
async def test_month_to_date_cost_per_run_averages_over_runs_not_calls():
    await _seed_jurisdiction()
    await _seed_jurisdiction(_OCDID_TWO)
    run_one = await factories.start_run(_OCDID)
    await record_calls(run_one, [_call("0.01"), _call("0.02")])
    run_two = await factories.start_run(_OCDID_TWO)
    await record_calls(run_two, [_call("0.09")])

    assert await get_month_to_date_cost_per_run(_STATE) == Decimal("0.06")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_month_to_date_cost_per_run_ignores_last_month_s_runs():
    """Last month's run would sit in the denominator with none of its money in the numerator."""
    await _seed_jurisdiction()
    now_run = await factories.start_run(_OCDID)
    await record_calls(now_run, [_call("0.02")])
    old_run = await factories.start_run(_OCDID)
    await record_calls(old_run, [_call("0.07")])
    await _backdate(old_run, 45)

    assert await get_month_to_date_cost_per_run(_STATE) == Decimal("0.02")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_month_to_date_cost_per_run_is_null_when_nothing_ran():
    """Null, not zero: no run this month is not a free run."""
    await _seed_jurisdiction()

    assert await get_month_to_date_cost_per_run(_STATE) is None


# --- Fleet averages, month to date ----------------------------------------------------
# Every state shares these figures, so other suites' rows can sit in them too: the assertions
# are bounds, not exact values.


@pytest.mark.asyncio
@pytest.mark.integration
async def test_fleet_cost_per_run_counts_this_month_s_runs():
    await _seed_jurisdiction()
    run = await factories.start_run(_OCDID)
    await record_calls(run, [_call("0.04")])

    assert await get_fleet_month_to_date_cost_per_run() is not None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_fleet_duration_ignores_runs_the_stale_sweep_gave_up_on():
    """An expired run's finished_at is when the sweep noticed, so its "duration" is noise."""
    await _seed_jurisdiction()
    await _seed_jurisdiction(_OCDID_TWO)
    succeeded = await factories.start_run(_OCDID)
    await factories.complete_run(succeeded)
    expired = await factories.start_run(_OCDID_TWO)
    await factories.backdate_run(expired, 20)
    await factories.fail_run(expired)

    seconds = await get_fleet_month_to_date_seconds_per_run()

    assert seconds is not None
    assert seconds < 10 * 86_400
