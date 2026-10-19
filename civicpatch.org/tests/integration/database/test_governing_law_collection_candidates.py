"""Who is due for a collection: never collected first, then a year old, never one in flight,
never a state. Real Postgres: the jsonb date and the run join are SQL.

Isolation: sentinel state 'zz', cleaned before and after.
"""

import json

import pytest
import pytest_asyncio

from database.database import get_pool
from database.governing_law import get_collection_candidates, has_unfinished_collection
from shared.utils.statuses import PipelineRunKind
from tests.integration import factories

_NEVER = "ocd-jurisdiction/country:us/state:zz/place:zz_never/government"
_STALE = "ocd-jurisdiction/country:us/state:zz/place:zz_stale/government"
_FRESH = "ocd-jurisdiction/country:us/state:zz/place:zz_fresh/government"
_STATE = "ocd-jurisdiction/country:us/state:zz/government"
_ALL = [_NEVER, _STALE, _FRESH, _STATE]


def _collected(collected_at: str) -> str:
    return json.dumps({"kind": "general_law", "classification": "town", "found_by": "classification", "source_page_ids": [],
                       "collected_at": collected_at, "cost_usd": None})


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
        for ocdid, level, law in [(_NEVER, "local", None), (_STALE, "local", _collected("2020-01-01T00:00:00Z")), (_FRESH, "local", _collected("2099-01-01T00:00:00Z")), (_STATE, "state", None)]:
            await cur.execute(
                "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level, data, extras_governing_law, updated_at) VALUES (%s, 'zz', %s, %s, %s, now())",
                (ocdid, level, json.dumps({"name": ocdid}), law),
            )
        await conn.commit()
    yield
    await _wipe()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_never_collected_comes_first_then_a_year_old_and_never_a_fresh_one_or_a_state():
    candidates = [c.jurisdiction_ocdid for c in await get_collection_candidates("zz", None)]

    assert candidates == [_NEVER, _STALE]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_collection_in_flight_is_not_a_candidate_and_a_scrape_does_not_count():
    await factories.start_run(_NEVER, kind=PipelineRunKind.GOVERNING_LAW_COLLECTOR)
    await factories.start_run(_STALE)

    assert [c.jurisdiction_ocdid for c in await get_collection_candidates("zz", None)] == [_STALE]
    assert await has_unfinished_collection(_NEVER)
    assert not await has_unfinished_collection(_STALE)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_limit_is_kept():
    assert len(await get_collection_candidates("zz", 1)) == 1
