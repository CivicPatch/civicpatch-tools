"""The Queue's bulk actions against the real test DB: a sheet import in a selection is refused.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import pytest
import pytest_asyncio

from database.database import get_pool
from database.users import SYSTEM_USER_ID
from services.bulk_review import dismiss_selected, publish_selected
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_bulk_review/government"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM activity WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM pipeline_runs WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def _clean():
    await _wipe()
    await factories.seed_jurisdiction(_OCDID, "zz")
    yield
    await _wipe()


async def _an_import() -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO changesets (kind, jurisdiction_ocdid) VALUES ('sheet_import', %s) "
            "RETURNING id::text",
            (_OCDID,),
        )
        row = await cur.fetchone()
        await conn.commit()
    assert row
    return row[0]


async def _a_scrape() -> str:
    return await factories.complete_run(await factories.start_run(_OCDID))


async def _state(changeset_id: str) -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT changeset_state FROM changesets WHERE id::text = %s", (changeset_id,)
        )
        row = await cur.fetchone()
    assert row
    return row[0]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_import_in_a_selection_is_not_published():
    imported = await _an_import()

    [result] = await publish_selected([imported], SYSTEM_USER_ID)

    assert result.changeset_id == imported
    assert result.published is False
    assert await _state(imported) == "open"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_dismissing_a_selection_skips_an_import():
    imported = await _an_import()
    scrape = await _a_scrape()

    assert await dismiss_selected([imported, scrape], SYSTEM_USER_ID) == [scrape]
    assert await _state(imported) == "open"
    assert await _state(scrape) == "dismissed"
