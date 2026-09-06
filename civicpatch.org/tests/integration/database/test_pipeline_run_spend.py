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

from database.pipeline_run_spend import get_state_spend
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


async def _row():
    return next((r for r in await get_state_spend() if r.state == _STATE), None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_state_that_ran_nothing_is_absent_rather_than_zero():
    """`not scraped` and `scraped for free` are different facts, and this query says so by
    omission — every state it returns spent something."""
    await _seed_jurisdiction()

    assert await _row() is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_spend_sums_the_window_s_calls_and_averages_per_run():
    await _seed_jurisdiction()
    await _seed_jurisdiction(_OCDID_TWO)
    run_one = await factories.start_run(_OCDID)
    await record_calls(run_one, [_call("0.01"), _call("0.02")])
    run_two = await factories.start_run(_OCDID_TWO)
    await record_calls(run_two, [_call("0.09")])

    row = await _row()

    assert row is not None
    assert row.spend_usd == Decimal("0.12")
    assert row.cost_per_scrape_usd == Decimal("0.06")  # two runs, not three calls


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_run_that_minted_no_changeset_still_counts():
    """Per *run*, not per changeset. A scrape that spent money and then failed before ingest
    produced nothing to review — leaving it out would flatter exactly the states that waste the
    most."""
    await _seed_jurisdiction()
    run_id = await factories.start_run(_OCDID)
    await record_calls(run_id, [_call("0.05")])
    await factories.fail_run(run_id)

    row = await _row()

    assert row is not None
    assert row.spend_usd == Decimal("0.05")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_window_before_this_one_is_reported_beside_it():
    """One scan, two windows — the page ranks states by whether spend is rising."""
    await _seed_jurisdiction()
    now_run = await factories.start_run(_OCDID)
    await record_calls(now_run, [_call("0.02")])
    then_run = await factories.start_run(_OCDID)
    await record_calls(then_run, [_call("0.07")])
    await _backdate(then_run, 45)  # inside the prior 30 days, outside the current

    row = await _row()

    assert row is not None
    assert row.spend_usd == Decimal("0.02")
    assert row.prior_spend_usd == Decimal("0.07")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_state_that_stopped_spending_still_appears_with_no_current_spend():
    """The drop to nothing is the signal the comparison exists to show, so the row has to
    survive. `spend_usd` is null, never 0 — it did not scrape for free."""
    await _seed_jurisdiction()
    then_run = await factories.start_run(_OCDID)
    await record_calls(then_run, [_call("0.07")])
    await _backdate(then_run, 45)

    row = await _row()

    assert row is not None
    assert row.spend_usd is None
    assert row.prior_spend_usd == Decimal("0.07")
    assert row.cost_per_scrape_usd is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_spend_older_than_both_windows_is_not_reported_at_all():
    await _seed_jurisdiction()
    ancient = await factories.start_run(_OCDID)
    await record_calls(ancient, [_call("9.99")])
    await _backdate(ancient, 200)

    assert await _row() is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_cost_per_scrape_averages_only_the_current_window_s_runs():
    """A prior-window run is in `prior_spend_usd`, so counting it in the denominator too would
    halve the current figure using money that is not in the numerator."""
    await _seed_jurisdiction()
    now_run = await factories.start_run(_OCDID)
    await record_calls(now_run, [_call("0.02")])
    then_run = await factories.start_run(_OCDID)
    await record_calls(then_run, [_call("0.07")])
    await _backdate(then_run, 45)

    row = await _row()

    assert row is not None
    assert row.cost_per_scrape_usd == Decimal("0.02")  # one run, not two
