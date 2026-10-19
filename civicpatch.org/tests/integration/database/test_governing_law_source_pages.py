"""`governing_law_source_pages` against real Postgres: inserted, read back only as its
jurisdiction's, and the same url collectable again.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

from datetime import timedelta

import pytest
import pytest_asyncio

from database.database import get_pool
from database.governing_law_source_pages import (
    get_governing_law_source_page,
    get_recent_governing_law_source_page,
    insert_governing_law_source_page,
)
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
    page = await insert_governing_law_source_page(_OCDID, _URL, "abc", "governing_law/abc.md", None)

    assert await get_governing_law_source_page(_OCDID, page.id) == page
    assert (page.source_url, page.page_hash, page.cache_path) == (_URL, "abc", "governing_law/abc.md")
    assert await get_governing_law_source_page(_OTHER, page.id) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_same_url_may_be_collected_again():
    first = await insert_governing_law_source_page(_OCDID, _URL, "abc", "governing_law/abc.md", None)
    second = await insert_governing_law_source_page(_OCDID, _URL, "def", "governing_law/def.md", None)

    assert first.id != second.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_newest_page_for_a_url_is_found_within_the_window_from_any_jurisdiction():
    page = await insert_governing_law_source_page(_OCDID, _URL, "abc", "governing_law/abc.md", None)

    recent = await get_recent_governing_law_source_page(_URL, timedelta(days=1))
    assert recent and (recent.id, recent.jurisdiction_ocdid) == (page.id, _OCDID)

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("UPDATE governing_law_source_pages SET collected_at = now() - interval '2 days' WHERE id = %s", (page.id,))
        await conn.commit()
    assert await get_recent_governing_law_source_page(_URL, timedelta(days=1)) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_reused_page_keeps_the_time_its_text_was_fetched():
    first = await insert_governing_law_source_page(_OCDID, _URL, "abc", "governing_law/abc.md", None)
    reused = await insert_governing_law_source_page(_OTHER, _URL, first.page_hash, first.cache_path, first.collected_at)

    assert (reused.jurisdiction_ocdid, reused.cache_path, reused.collected_at) == (_OTHER, first.cache_path, first.collected_at)
