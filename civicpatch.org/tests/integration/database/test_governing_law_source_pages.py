"""`governing_law_source_pages` against real Postgres: inserted, read back only as its
jurisdiction's, and the same url collectable again.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import pytest
import pytest_asyncio

from database.database import get_pool
from database.governing_law_source_pages import get_governing_law_source_page, insert_governing_law_source_page
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_law_pages/government"
_OTHER = "ocd-jurisdiction/country:us/state:zz/place:zz_law_pages_other/government"
_URL = "https://legislature.vermont.gov/statutes/section/24/039/01304"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM governing_law_source_pages WHERE jurisdiction_ocdid = ANY(%s)", ([_OCDID, _OTHER],))
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = ANY(%s)", ([_OCDID, _OTHER],))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def _clean():
    await _wipe()
    await factories.seed_jurisdiction(_OCDID, "zz")
    await factories.seed_jurisdiction(_OTHER, "zz")
    yield
    await _wipe()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_page_is_read_back_only_by_its_jurisdiction():
    page = await insert_governing_law_source_page(_OCDID, _URL, "abc", "governing_law/abc.md")

    assert await get_governing_law_source_page(_OCDID, page.id) == page
    assert (page.source_url, page.page_hash, page.cache_path) == (_URL, "abc", "governing_law/abc.md")
    assert await get_governing_law_source_page(_OTHER, page.id) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_same_url_may_be_collected_again():
    first = await insert_governing_law_source_page(_OCDID, _URL, "abc", "governing_law/abc.md")
    second = await insert_governing_law_source_page(_OCDID, _URL, "def", "governing_law/def.md")

    assert first.id != second.id
