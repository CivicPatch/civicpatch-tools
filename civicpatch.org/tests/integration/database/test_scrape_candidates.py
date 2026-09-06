"""The candidate pool: due = off this state's cadence cooldown, measured from the last attempt.

Real Postgres — the whole thing is a join against `pipeline_runs` and `state_settings`.

Isolation: sentinel state 'zv'.
"""

import datetime
import uuid

import pytest
import pytest_asyncio

from database.database import get_pool
from database.jurisdictions import get_stale_jurisdictions
from database.state_settings import set_cadence

_STATE = "zv"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM pipeline_runs WHERE jurisdiction_ocdid LIKE 'ocd-%state:zv%'"
        )
        await cur.execute("DELETE FROM jurisdictions WHERE state = %s", (_STATE,))
        await cur.execute("DELETE FROM state_settings WHERE state = %s", (_STATE,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def _clean():
    await _wipe()
    yield
    await _wipe()


def _ocdid(place: str) -> str:
    return f"ocd-jurisdiction/country:us/state:{_STATE}/place:{place}/government"


async def _jurisdiction(place: str) -> str:
    ocdid = _ocdid(place)
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level, data, updated_at, status) "
            "VALUES (%s, %s, 'local', %s::jsonb, now(), 'active')",
            (ocdid, _STATE, '{"name": "P", "url": "https://x"}'),
        )
        await conn.commit()
    return ocdid


async def _attempt(ocdid: str, days_ago: int, status: str = "ERROR") -> None:
    """A run, however it ended. The point is that it was *tried*."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO pipeline_runs (id, jurisdiction_ocdid, arguments_json, status, "
            "created_at, finished_at) VALUES (%s, %s, '{}'::jsonb, %s, "
            "now() - make_interval(days => %s), now() - make_interval(days => %s))",
            (str(uuid.uuid4()), ocdid, status, days_ago, days_ago),
        )
        await conn.commit()


async def _due() -> list[str]:
    return [j.id for j in await get_stale_jurisdictions(_STATE)]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_state_with_no_cadence_is_still_on_a_cooldown():
    """NULL cadence means no schedule. It used to mean no cooldown as well, and that is the
    bug: a jurisdiction that scraped cleanly and auto-published was eligible again the moment
    its run went terminal, so a state scrape given no `num_jurisdictions` never ran out of
    candidates and never stopped."""
    ocdid = await _jurisdiction("no-cadence")
    await _attempt(ocdid, days_ago=0)

    assert await _due() == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_state_with_no_cadence_comes_back_off_the_default():
    """The other half: the fallback is a cooldown, not a permanent exclusion. Without this a
    bug that blocked every unconfigured state forever would read as a pass above."""
    ocdid = await _jurisdiction("no-cadence-aged")
    await _attempt(ocdid, days_ago=31)

    assert await _due() == [ocdid]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_failed_run_still_counts_as_having_been_tried():
    """The bug this fixes: an errored run publishes nothing, so a pool keyed on publishes
    re-offered it immediately and burned the same budget again."""
    ocdid = await _jurisdiction("errored")
    await set_cadence(_STATE, 30, None, None)
    await _attempt(ocdid, days_ago=1, status="ERROR")

    assert await _due() == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_it_comes_back_once_the_cadence_has_passed():
    ocdid = await _jurisdiction("aged")
    await set_cadence(_STATE, 30, None, None)
    await _attempt(ocdid, days_ago=31)

    assert await _due() == [ocdid]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_never_tried_comes_before_longest_since_tried():
    never = await _jurisdiction("never")
    old = await _jurisdiction("old")
    recent = await _jurisdiction("recent")
    await set_cadence(_STATE, 7, None, None)
    await _attempt(old, days_ago=40)
    await _attempt(recent, days_ago=8)

    assert await _due() == [never, old, recent]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_place_tried_repeatedly_stops_leading_the_queue():
    """Ordering on the last *publish* left a place scraped ten times and never published at the
    head forever, because its publish date never moved."""
    tried = await _jurisdiction("tried")
    untried = await _jurisdiction("untouched")
    await set_cadence(_STATE, 7, None, None)
    for days in (60, 40, 20, 8):
        await _attempt(tried, days_ago=days)

    assert await _due() == [untried, tried]
