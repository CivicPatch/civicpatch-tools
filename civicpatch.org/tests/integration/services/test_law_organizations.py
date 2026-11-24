"""A place's organizations follow its law once pipeline 2 has answered, on real Postgres: the law's are
created, an empty one it does not name goes, and one still holding people stays, as does the default."""

import json
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from database.database import get_pool
from services.law_organizations import apply_law_organizations
from shared.schemas import GoverningLawOrganizations
from tests.integration import factories

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_PLACE = "ocd-jurisdiction/country:us/state:zz/place:zylaw/government"
_AT = datetime(2026, 11, 1, tzinfo=timezone.utc)


def _answer(*organizations: str) -> GoverningLawOrganizations:
    return GoverningLawOrganizations.model_validate({
        "posts": [
            {
                "role": "member", "label": "Member", "organization_id": organization,
                "sources": [{"url": "https://example.gov/charter", "note": "five members",
                             "extras": {"source_page_id": "p1", "matched_in": "sentence"}}],
            }
            for organization in organizations
        ],
        "extras": {"governing_law_collected_at": "2026-11-01T00:00:00Z"},
    })


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM source_records WHERE jurisdiction_ocdid = %s", (_PLACE,))
        await cur.execute("DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_PLACE,))
        await cur.execute("DELETE FROM organizations WHERE jurisdiction_ocdid = %s", (_PLACE,))
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_PLACE,))
        await conn.commit()


async def _organization(name: str, is_default: bool = False) -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO organizations (jurisdiction_ocdid, name, meta_is_default) VALUES (%s, %s, %s) RETURNING id::text",
            (_PLACE, name, is_default),
        )
        row = await cur.fetchone()
        await conn.commit()
    assert row
    return row[0]


async def _names() -> set[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT name FROM organizations WHERE jurisdiction_ocdid = %s", (_PLACE,))
        return {row[0] for row in await cur.fetchall()}


@pytest_asyncio.fixture(autouse=True)
async def _seeded():
    await _wipe()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, data, updated_at) VALUES (%s, 'zz', %s, now())",
            (_PLACE, json.dumps({"name": "Zylaw town"})),
        )
        await conn.commit()
    await _organization("Zylaw Officers", is_default=True)
    await _organization("Council")
    await _organization("Town Meeting")
    selectboard = await _organization("Selectboard")
    await factories.published_source_record(
        _PLACE, selectboard, "7a3e1f00-0000-4000-8000-00000000a1a1", "Ada Example", "Selectboard Member", "https://example.gov/board", _AT
    )
    yield
    await _wipe()


async def test_the_law_decides_the_organizations_but_nobody_is_moved():
    await apply_law_organizations(_PLACE, _answer("Council", "Board of Finance"))

    # Board of Finance is new; Town Meeting was empty and is gone; Selectboard keeps its person until a
    # rescrape; the default always stays.
    assert await _names() == {"Zylaw Officers", "Council", "Board of Finance", "Selectboard"}


async def test_an_answer_naming_no_posts_changes_nothing():
    await apply_law_organizations(_PLACE, _answer())

    assert await _names() == {"Zylaw Officers", "Council", "Town Meeting", "Selectboard"}
