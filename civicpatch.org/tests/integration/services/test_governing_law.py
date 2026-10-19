"""Saving a jurisdiction's governing law: written over what was there, read back as the model,
and logged as an edit of the jurisdiction."""

import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest
import pytest_asyncio

from database.database import get_pool
from database.users import SYSTEM_USER_ID
from services.governing_law import UnknownJurisdiction, collector_config, get_governing_law, set_governing_law
from shared.schemas import FoundBy, GoverningLaw, GoverningLawKind
from shared.utils.layered_config import ConfigFile

_TOWN = "ocd-jurisdiction/country:us/state:vt/place:zylaw_town/government"
_UNKNOWN = "ocd-jurisdiction/country:us/state:vt/place:zylaw_nowhere/government"

_CHARTER = GoverningLaw(
    kind=GoverningLawKind.CHARTER,
    classification="town",
    found_by=FoundBy.STATE_INDEX,
    source_page_ids=["5d3e2c6a-0c4b-4b8e-9a2d-1f6e7c8b9a01"],
    collected_at=datetime(2026, 10, 18, 12, tzinfo=timezone.utc),
    cost_usd=None,
)
_GENERAL_LAW = GoverningLaw(
    kind=GoverningLawKind.GENERAL_LAW,
    classification="town",
    found_by=FoundBy.SEARCH,
    source_page_ids=[],
    collected_at=datetime(2027, 10, 18, 12, tzinfo=timezone.utc),
    cost_usd=Decimal("0.0031"),
)


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM activity WHERE jurisdiction_ocdid = %s", (_TOWN,))
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_TOWN,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def _seeded():
    await _wipe()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, data, updated_at) VALUES (%s, 'vt', %s, now())",
            (_TOWN, json.dumps({"name": "Zylaw town"})),
        )
        await conn.commit()
    yield
    await _wipe()


async def _edits() -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT changes FROM activity WHERE jurisdiction_ocdid = %s AND type = 'edit_jurisdiction' ORDER BY created_at",
            (_TOWN,),
        )
        return [row[0] for row in await cur.fetchall()]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_nothing_until_a_run_has_written_it():
    assert await get_governing_law(_TOWN) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_written_then_read_back_whole():
    await set_governing_law(_TOWN, _CHARTER, None)

    assert await get_governing_law(_TOWN) == _CHARTER


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_later_run_replaces_the_answer_and_both_are_logged():
    await set_governing_law(_TOWN, _CHARTER, None)
    await set_governing_law(_TOWN, _GENERAL_LAW, SYSTEM_USER_ID)

    assert await get_governing_law(_TOWN) == _GENERAL_LAW
    first, second = await _edits()
    assert first["fields"][0]["before"] is None
    assert first["fields"][0]["after"]["kind"] == "charter"
    assert second["fields"][0]["before"]["kind"] == "charter"
    assert second["fields"][0]["after"]["cost_usd"] == "0.0031"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_an_unknown_jurisdiction_is_refused():
    with pytest.raises(UnknownJurisdiction):
        await set_governing_law(_UNKNOWN, _CHARTER, None)
    assert await get_governing_law(_UNKNOWN) is None


_STATE_CONFIG_PATH = "data_source/zz/local/config.yml"
_ZZ_TOWN = "ocd-jurisdiction/country:us/state:zz/place:zylaw_town/government"
_COUNTY = "ocd-jurisdiction/country:us/state:zz/county:zylaw/government"


@pytest_asyncio.fixture
async def zz_governing_law():
    """A state file with a governing_law block, and a town and a county in the sentinel state 'zz'."""
    content = ConfigFile.model_validate({
        "governing_law": {
            "charter_terms": ["Charter"],
            "classifications": {"town": {"lsad": ["town"], "governed_by": "charter_or_general_law", "general_law": ["https://zz.gov/statutes/1"]}},
        }
    })
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdiction_configs (path, content, commit_sha) VALUES (%s, %s, 'test') "
            "ON CONFLICT (path) DO UPDATE SET content = EXCLUDED.content",
            (_STATE_CONFIG_PATH, content.model_dump_json()),
        )
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level, data, updated_at) VALUES "
            "(%s, 'zz', 'local', %s, now()), (%s, 'zz', 'counties', %s, now())",
            (_ZZ_TOWN, json.dumps({"name": "Zylaw town"}), _COUNTY, json.dumps({"name": "Zylaw County"})),
        )
        await conn.commit()
    yield content.governing_law
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM jurisdiction_configs WHERE path = %s", (_STATE_CONFIG_PATH,))
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = ANY(%s)", ([_ZZ_TOWN, _COUNTY],))
        await conn.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_collector_is_told_its_states_block_for_its_level(zz_governing_law):
    town = await collector_config(_ZZ_TOWN)
    county = await collector_config(_COUNTY)

    assert (town.name, town.governing_law) == ("Zylaw town", zz_governing_law)
    # The counties file has no block, so a county is told none.
    assert (county.name, county.governing_law) == ("Zylaw County", None)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_an_unknown_jurisdiction_has_no_collector_config():
    with pytest.raises(UnknownJurisdiction):
        await collector_config(_UNKNOWN)
