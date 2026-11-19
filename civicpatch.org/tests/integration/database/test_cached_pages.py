"""Integration tests for `database.source_pages.get_cached_pages`: the cached pages a review card
may link to.

Against the real test DB, because the rule is a WHERE clause: the card's own run's rows whether or
not they published, a published run's rows, never an unpublished or withdrawn one, never a row that
cached nothing.

Isolation: sentinel jurisdictions, removed before and after each test.
"""
import datetime
import uuid

import pytest
import pytest_asyncio

from core.source_pages import CachedPage, SourcePageRow
from database.claims import withdraw_facts
from database.database import get_pool
from database.source_pages import get_cached_pages, insert_source_pages
from database.users import SYSTEM_USER_ID
from schemas.claims import EntityType

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_cached_pages/government"
_OTHER_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_cached_pages_two/government"
_URL = "https://zz.gov/selectboard"
_T0 = datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc)
_T1 = datetime.datetime(2026, 6, 1, tzinfo=datetime.timezone.utc)


async def _cleanup():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        for ocdid in (_OCDID, _OTHER_OCDID):
            await cur.execute(
                "DELETE FROM claims WHERE changeset_id IN "
                "(SELECT id FROM changesets WHERE jurisdiction_ocdid = %s)",
                (ocdid,),
            )
            await cur.execute("DELETE FROM pipeline_runs WHERE jurisdiction_ocdid = %s", (ocdid,))
            await cur.execute("DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (ocdid,))
            await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (ocdid,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def sentinel_jurisdictions():
    await _cleanup()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        for ocdid in (_OCDID, _OTHER_OCDID):
            await cur.execute("INSERT INTO jurisdictions (jurisdiction_ocdid) VALUES (%s)", (ocdid,))
        await conn.commit()
    yield
    await _cleanup()


async def _scrape(
    at: datetime.datetime,
    published: bool = True,
    ocdid: str = _OCDID,
    url: str = _URL,
    cache_path: str | None = "cache",
    unchanged_since_source_page_id: str | None = None,
) -> tuple[str, str]:
    """One scrape of `url`: its changeset, run and page row. Returns (changeset id, run id)."""
    changeset_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO changesets (id, kind, jurisdiction_ocdid, published_at) "
            "VALUES (%s, 'scrape', %s, %s)",
            (changeset_id, ocdid, at if published else None),
        )
        await cur.execute(
            "INSERT INTO pipeline_runs (id, kind, jurisdiction_ocdid, arguments_json, changeset_id) "
            "VALUES (%s, 'people_collector', %s, '{}', %s)",
            (run_id, ocdid, changeset_id),
        )
        await conn.commit()
    await insert_source_pages(
        [
            SourcePageRow(
                source_url=url,
                jurisdiction_ocdid=ocdid,
                pipeline_run_id=run_id,
                changeset_id=changeset_id,
                organization_ids=[],
                page_hash="p",
                prompt_hash="q",
                cache_path=f"{cache_path}/{run_id}" if cache_path else None,
                anchor_text=None,
                is_relevant=True,
                relevant_urls=[],
                heuristics_failures=[],
                unchanged_since_source_page_id=unchanged_since_source_page_id,
            )
        ]
    )
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE source_pages SET created_at = %s WHERE pipeline_run_id = %s",
            (at, run_id),
        )
        await conn.commit()
    return changeset_id, run_id


async def _row_id(run_id: str) -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT id::text FROM source_pages WHERE pipeline_run_id = %s", (run_id,))
        return (await cur.fetchone())[0]


def _runs(cached_pages: list[CachedPage]) -> list[str]:
    return sorted(page.pipeline_run_id for page in cached_pages)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_cards_own_run_is_a_cached_page_whether_it_published_or_not():
    _, run_id = await _scrape(_T1, published=False)

    [cached_page] = await get_cached_pages([_OCDID], [run_id])

    assert cached_page.pipeline_run_id == run_id
    assert cached_page.source_url == _URL
    assert cached_page.cache_path == f"cache/{run_id}"
    assert cached_page.cached_at == _T1
    assert cached_page.is_published is False


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_published_runs_cached_page_is_offered_and_an_unpublished_one_is_not():
    _, published = await _scrape(_T0)
    await _scrape(_T1, published=False)

    [cached_page] = await get_cached_pages([_OCDID], [])

    assert cached_page.pipeline_run_id == published
    assert cached_page.is_published is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_withdrawn_rows_cached_page_is_never_offered():
    changeset_id, withdrawn = await _scrape(_T0)
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await withdraw_facts(
            cur, EntityType.SOURCE_PAGE, [await _row_id(withdrawn)], SYSTEM_USER_ID, changeset_id
        )
        await conn.commit()

    assert await get_cached_pages([_OCDID], []) == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_row_that_cached_nothing_is_not_a_cached_page():
    _, run_id = await _scrape(_T0, cache_path=None, url="https://zz.gov/unfetched")

    assert await get_cached_pages([_OCDID], [run_id]) == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_row_that_reused_a_published_reading_links_its_own_cached_page():
    _, read = await _scrape(_T0)
    _, reused = await _scrape(_T1, unchanged_since_source_page_id=await _row_id(read))

    cached_pages = await get_cached_pages([_OCDID], [reused])

    [own] = [page for page in cached_pages if page.pipeline_run_id == reused]
    assert (own.cached_at, own.cache_path) == (_T1, f"cache/{reused}")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_one_url_in_two_jurisdictions_comes_back_once_per_jurisdiction():
    _, first = await _scrape(_T0)
    _, second = await _scrape(_T0, ocdid=_OTHER_OCDID)

    cached_pages = await get_cached_pages([_OCDID, _OTHER_OCDID], [])

    assert sorted((page.jurisdiction_ocdid, page.pipeline_run_id) for page in cached_pages) == sorted(
        [(_OCDID, first), (_OTHER_OCDID, second)]
    )
