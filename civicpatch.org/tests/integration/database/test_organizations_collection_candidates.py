"""Who is due for organizations collection: has a governing law, no organizations or
stale ones. Never-collected first, never without a governing law, never a state.
Real Postgres: the jsonb dates and the run join are SQL.

Isolation: sentinel state 'zz', cleaned before and after.
"""

import json

import pytest
import pytest_asyncio
from database.database import get_pool
from database.governing_law import get_organizations_collection_candidates
from database.pipeline_runs import has_unfinished_run
from shared.utils.statuses import PipelineRunKind

from tests.integration import factories

_NEVER_ORG = "ocd-jurisdiction/country:us/state:zz/place:zz_never_org/government"
_STALE_ORG = "ocd-jurisdiction/country:us/state:zz/place:zz_stale_org/government"
_FRESH_ORG = "ocd-jurisdiction/country:us/state:zz/place:zz_fresh_org/government"
_NO_LAW = "ocd-jurisdiction/country:us/state:zz/place:zz_no_law/government"
_STATE = "ocd-jurisdiction/country:us/state:zz/government"
_ALL = [_NEVER_ORG, _STALE_ORG, _FRESH_ORG, _NO_LAW, _STATE]


def _governing_law(collected_at: str, kind: str = "charter") -> str:
    return json.dumps({
        "kind": kind, "classification": "town", "found_by": "classification",
        "source_page_ids": [], "collected_at": collected_at, "cost_usd": None,
    })


def _organizations(governing_law_collected_at: str) -> str:
    return json.dumps({"posts": [], "extras": {"governing_law_collected_at": governing_law_collected_at}})


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM pipeline_runs WHERE jurisdiction_ocdid = ANY(%s)", (_ALL,))
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = ANY(%s)", (_ALL,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def _seeded():
    await _wipe()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        for ocdid, level, law, orgs in [
            # Has governing law, no organizations yet → candidate
            (_NEVER_ORG, "local", _governing_law("2026-01-01T00:00:00Z"), None),
            # Has organizations but older than governing law → candidate
            (_STALE_ORG, "local", _governing_law("2026-06-01T00:00:00Z"), _organizations("2020-01-01T00:00:00Z")),
            # Has organizations as new as governing law → not a candidate
            (_FRESH_ORG, "local", _governing_law("2026-01-01T00:00:00Z"), _organizations("2026-01-01T00:00:00Z")),
            # No governing law → not a candidate
            (_NO_LAW, "local", None, None),
            # State level → not a candidate
            (_STATE, "state", None, None),
        ]:
            await cur.execute(
                """INSERT INTO jurisdictions
                   (jurisdiction_ocdid, state, level, data, extras_governing_law, extras_organizations, updated_at)
                   VALUES (%s, 'zz', %s, %s, %s, %s, now())""",
                (ocdid, level, json.dumps({"name": ocdid}), law, orgs),
            )
        await conn.commit()
    yield
    await _wipe()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_never_collected_orgs_comes_first_then_stale():
    candidates = [c.jurisdiction_ocdid for c in await get_organizations_collection_candidates("zz", None)]

    assert candidates == [_NEVER_ORG, _STALE_ORG]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_jurisdiction_without_governing_law_is_not_a_candidate():
    candidates = [c.jurisdiction_ocdid for c in await get_organizations_collection_candidates("zz", None)]

    assert _NO_LAW not in candidates
    assert _STATE not in candidates


@pytest.mark.integration
@pytest.mark.asyncio
async def test_an_organizations_collection_in_flight_is_not_a_candidate():
    await factories.start_run(_NEVER_ORG, kind=PipelineRunKind.ORGANIZATIONS_COLLECTOR)

    assert [c.jurisdiction_ocdid for c in await get_organizations_collection_candidates("zz", None)] == [_STALE_ORG]
    assert await has_unfinished_run(_NEVER_ORG, PipelineRunKind.ORGANIZATIONS_COLLECTOR)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_limit_is_kept():
    assert len(await get_organizations_collection_candidates("zz", 1)) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_collection_that_failed_today_is_not_claimed_again():
    run_id = await factories.start_run(_NEVER_ORG, kind=PipelineRunKind.ORGANIZATIONS_COLLECTOR)
    await factories.fail_run(run_id)

    assert [c.jurisdiction_ocdid for c in await get_organizations_collection_candidates("zz", None)] == [_STALE_ORG]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_people_collector_run_does_not_block_organizations_collection():
    await factories.start_run(_NEVER_ORG, kind=PipelineRunKind.PEOPLE_COLLECTOR)

    assert [c.jurisdiction_ocdid for c in await get_organizations_collection_candidates("zz", None)] == [_NEVER_ORG, _STALE_ORG]
