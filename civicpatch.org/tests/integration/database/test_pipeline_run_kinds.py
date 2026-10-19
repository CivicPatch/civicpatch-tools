"""A collector's run shares the run machinery but not the scrape's scheduling (migration 248).

Each test starts a governing-law collector run beside, or instead of, a scrape and asks one of
the scrape-only queries: the cooldown, the unfinished-run sets, the in-flight lane, the per-run
averages, the scrape's monthly budget. A collection is bounded by its kind's own caps instead.

Real Postgres: the filters are SQL. Isolation: sentinel state 'zz', cleaned before and after.
"""

from typing import LiteralString, cast

from decimal import Decimal

import pytest
import pytest_asyncio

from database import changeset_predicates
from database.changesets import get_in_flight
from database.database import get_pool
from database.collector_settings import get_collector_settings, set_collector_caps
from database.issue_listings import count_collector_cost_cap_hits_this_month, count_cost_cap_hits_this_month
from database.pipeline_run_spend import (
    get_collector_month_to_date_runs,
    get_collector_month_to_date_spend,
    get_fleet_month_to_date_cost_per_run,
    get_fleet_month_to_date_seconds_per_run,
    get_month_to_date_cost_per_run,
    get_month_to_date_spend,
)
from database.pipeline_runs import (
    jurisdiction_ocdids_with_unfinished_runs,
    jurisdiction_ocdids_with_unfinished_runs_in_state,
)
from shared.utils.statuses import PipelineIssueType, PipelineRunKind, PipelineRunStatus
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_run_kinds/government"
_COLLECTOR = PipelineRunKind.GOVERNING_LAW_COLLECTOR


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM pipeline_runs WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def _clean():
    await _wipe()
    await factories.seed_jurisdiction(_OCDID, "zz")
    yield
    await _wipe()


async def _finish(run_id: str, seconds: int) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE pipeline_runs
            SET status = %s, finished_at = now(), created_at = now() - make_interval(secs => %s)
            WHERE id = %s
            """,
            (PipelineRunStatus.SUCCESS, seconds, run_id),
        )
        await conn.commit()


async def _spend(run_id: str, cost_usd: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO llm_calls (
                pipeline_run_id, prompt_name, attempt, gateway, model, routed_model,
                upstream_provider, input_tokens, output_tokens, cost_usd
            )
            VALUES (%s, 'find_governing_law', 1, 'google', 'gemini', 'gemini', 'Google', 1, 1, %s)
            """,
            (run_id, cost_usd),
        )
        await conn.commit()


async def _last_attempt_at():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        # Spliced from the module's own constants, as get_stale_jurisdictions does.
        query = cast(
            LiteralString,
            f"SELECT {changeset_predicates.LAST_ATTEMPT_AT} FROM jurisdictions j "
            f"{changeset_predicates.LAST_ATTEMPT_JOIN} WHERE j.jurisdiction_ocdid = %s",
        )
        await cur.execute(query, (_OCDID,))
        row = await cur.fetchone()
        assert row
        return row[0]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_collection_does_not_date_the_scrapes_last_attempt():
    await factories.start_run(_OCDID, kind=_COLLECTOR)

    assert await _last_attempt_at() is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_collection_in_flight_does_not_block_a_scrape():
    await factories.start_run(_OCDID, kind=_COLLECTOR)

    assert _OCDID not in await jurisdiction_ocdids_with_unfinished_runs()
    assert _OCDID not in await jurisdiction_ocdids_with_unfinished_runs_in_state("zz")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_scrape_in_flight_still_does():
    await factories.start_run(_OCDID)

    assert _OCDID in await jurisdiction_ocdids_with_unfinished_runs()
    assert _OCDID in await jurisdiction_ocdids_with_unfinished_runs_in_state("zz")
    assert await _last_attempt_at() is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_collection_is_not_in_the_jurisdictions_scrape_lane():
    await factories.start_run(_OCDID, kind=_COLLECTOR)
    scrape_id = await factories.start_run(_OCDID)

    assert [entry.id for entry in (await get_in_flight(_OCDID)).in_flight] == [scrape_id]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_collections_cost_and_time_stay_out_of_the_per_scrape_averages():
    fleet_cost_before = await get_fleet_month_to_date_cost_per_run()
    fleet_seconds_before = await get_fleet_month_to_date_seconds_per_run()
    run_id = await factories.start_run(_OCDID, kind=_COLLECTOR)
    await _spend(run_id, "50")
    await _finish(run_id, 86_400)

    assert await get_month_to_date_cost_per_run("zz") is None
    assert await get_fleet_month_to_date_cost_per_run() == fleet_cost_before
    assert await get_fleet_month_to_date_seconds_per_run() == fleet_seconds_before


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_collections_spend_counts_against_its_own_month_not_the_scrapes():
    """The admin's monthly caps bound scrapes; a collector kind has its own (migration 249)."""
    before = await get_collector_month_to_date_spend(_COLLECTOR)
    run_id = await factories.start_run(_OCDID, kind=_COLLECTOR)
    await _spend(run_id, "0.25")

    state_spent, _ = await get_month_to_date_spend("zz")
    assert state_spent == 0
    assert await get_collector_month_to_date_spend(_COLLECTOR) - before == pytest.approx(Decimal("0.25"))


async def _cap(run_id: str):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT pipeline_run_cap_usd FROM pipeline_runs WHERE id = %s", (run_id,))
        row = await cur.fetchone()
        assert row
        return row[0]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_collection_runs_under_its_kinds_cap_and_a_scrape_under_its_states():
    settings = await get_collector_settings(_COLLECTOR)
    await set_collector_caps(_COLLECTOR, Decimal("0.75"), settings.monthly_cap_usd, None)
    try:
        collection = await factories.start_run(_OCDID, kind=_COLLECTOR)
        scrape = await factories.start_run(_OCDID)

        assert await _cap(collection) == Decimal("0.75")
        # 'zz' has no state_settings row: a scrape inherits pipeline.yml's default.
        assert await _cap(scrape) is None
    finally:
        await set_collector_caps(_COLLECTOR, settings.pipeline_run_cap_usd, settings.monthly_cap_usd, settings.updated_by_user_id)



@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_collections_runs_and_cap_hits_are_its_kinds_not_the_states():
    runs_before, _ = await get_collector_month_to_date_runs(_COLLECTOR)
    hits_before = await count_collector_cost_cap_hits_this_month(_COLLECTOR)
    run_id = await factories.start_run(_OCDID, kind=_COLLECTOR)
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO pipeline_run_issues (pipeline_run_id, issue_type, status) VALUES (%s, %s, 'pending')",
            (run_id, PipelineIssueType.COST_CAP_REACHED),
        )
        await conn.commit()

    runs_after, _ = await get_collector_month_to_date_runs(_COLLECTOR)
    assert runs_after - runs_before == 1
    assert await count_collector_cost_cap_hits_this_month(_COLLECTOR) - hits_before == 1
    assert await count_cost_cap_hits_this_month("zz") == 0
