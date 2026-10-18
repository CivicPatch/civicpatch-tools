"""Saving a jurisdiction's governing law: written over what was there, read back as the model,
and logged as an edit of the jurisdiction."""

import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest
import pytest_asyncio

from database.database import get_pool
from database.users import SYSTEM_USER_ID
from services.governing_law import UnknownJurisdiction, get_governing_law, set_governing_law
from shared.schemas import Finder, GoverningLaw, GoverningLawKind

_TOWN = "ocd-jurisdiction/country:us/state:vt/place:zylaw_town/government"
_UNKNOWN = "ocd-jurisdiction/country:us/state:vt/place:zylaw_nowhere/government"

_CHARTER = GoverningLaw(
    kind=GoverningLawKind.CHARTER,
    classification="town",
    finder=Finder.STATE_INDEX,
    source_page_ids=["5d3e2c6a-0c4b-4b8e-9a2d-1f6e7c8b9a01"],
    collected_at=datetime(2026, 10, 18, 12, tzinfo=timezone.utc),
    cost_usd=None,
)
_GENERAL_LAW = GoverningLaw(
    kind=GoverningLawKind.GENERAL_LAW,
    classification="town",
    finder=Finder.SEARCH,
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
