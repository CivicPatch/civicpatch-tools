"""Integration tests for `database.source_pages.published_source_pages`: what `/config` offers a run to reuse.

Against the real test DB, because every rule here is a WHERE clause: published only, latest per
url, never a withdrawn row or record, never a page whose extraction failed.

Isolation: one sentinel jurisdiction, removed before and after each test.
"""
import datetime
import uuid

import pytest
import pytest_asyncio

from core.source_pages import SourcePageRow
from database.claims import withdraw_facts
from database.database import get_pool
from database.source_pages import insert_source_pages, published_source_pages
from database.source_records import insert_source_records
from database.users import SYSTEM_USER_ID
from schemas.claims import EntityType

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_known_pages/government"
_ORGANIZATION = "00000000-0000-4000-8000-0000000000d1"
_PERSON = "00000000-0000-4000-8000-0000000000d2"
_URL = "https://zz.gov/council"
_T0 = datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc)
_T1 = datetime.datetime(2026, 6, 1, tzinfo=datetime.timezone.utc)


async def _cleanup():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM claims WHERE changeset_id IN "
            "(SELECT id FROM changesets WHERE jurisdiction_ocdid = %s)",
            (_OCDID,),
        )
        await cur.execute("DELETE FROM pipeline_runs WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM organizations WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def sentinel_jurisdiction():
    await _cleanup()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("INSERT INTO jurisdictions (jurisdiction_ocdid) VALUES (%s)", (_OCDID,))
        await cur.execute(
            "INSERT INTO organizations (id, jurisdiction_ocdid, name) VALUES (%s, %s, 'Council')",
            (_ORGANIZATION, _OCDID),
        )
        await conn.commit()
    yield
    await _cleanup()


async def _scrape(at: datetime.datetime, published: bool = True, **page_fields) -> tuple[str, str]:
    """One scrape of `_URL`: its changeset, run and page row. Returns (changeset id, row id)."""
    changeset_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO changesets (id, kind, jurisdiction_ocdid, published_at) "
            "VALUES (%s, 'scrape', %s, %s)",
            (changeset_id, _OCDID, at if published else None),
        )
        await cur.execute(
            "INSERT INTO pipeline_runs (id, jurisdiction_ocdid, arguments_json, changeset_id) "
            "VALUES (%s, %s, '{}', %s)",
            (run_id, _OCDID, changeset_id),
        )
        await conn.commit()
    fields = {
        "page_hash": "p",
        "prompt_hash": "q",
        "is_relevant": True,
        "organization_ids": [_ORGANIZATION],
        "relevant_urls": [],
        "heuristics_failures": [],
        **page_fields,
    }
    await insert_source_pages(
        [
            SourcePageRow(
                source_url=_URL,
                jurisdiction_ocdid=_OCDID,
                pipeline_run_id=run_id,
                changeset_id=changeset_id,
                cache_path=None,
                anchor_text=None,
                **fields,
            )
        ]
    )
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE source_pages SET created_at = %s WHERE pipeline_run_id = %s RETURNING id::text",
            (at, run_id),
        )
        row_id = (await cur.fetchone())[0]
        await conn.commit()
    return changeset_id, row_id


async def _withdraw(entity_type: EntityType, entity_id: str, changeset_id: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await withdraw_facts(cur, entity_type, [entity_id], SYSTEM_USER_ID, changeset_id)
        await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_latest_published_row_is_offered_and_an_unpublished_one_is_not():
    await _scrape(_T0, page_hash="old")
    _, latest = await _scrape(_T1, page_hash="new")
    await _scrape(_T1 + datetime.timedelta(days=1), published=False, page_hash="unreviewed")

    [page] = await published_source_pages(_OCDID)

    assert (page.page_hash, page.read_source_page_id) == ("new", latest)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_page_whose_extraction_failed_is_never_offered():
    await _scrape(_T0, heuristics_failures=["name_not_in_text"])

    assert await published_source_pages(_OCDID) == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_withdrawn_row_is_never_offered():
    """A rolled-back scrape must not seed a replay; the earlier row stands again."""
    _, earlier = await _scrape(_T0)
    changeset_id, later = await _scrape(_T1)
    await _withdraw(EntityType.SOURCE_PAGE, later, changeset_id)

    [page] = await published_source_pages(_OCDID)

    assert page.read_source_page_id == earlier


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_reused_row_points_back_at_the_real_read():
    _, read = await _scrape(_T0)
    _, reused = await _scrape(_T1)
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE source_pages SET unchanged_since_source_page_id = %s WHERE id = %s",
            (read, reused),
        )

    [page] = await published_source_pages(_OCDID)

    assert page.read_source_page_id == read


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_page_comes_with_its_live_records_and_their_photos():
    changeset_id, _ = await _scrape(_T0)
    await insert_source_records(
        changeset_id,
        _OCDID,
        {
            _PERSON: [
                {"name": "Ana Reyes", "label": "Mayor", "source_url": _URL,
                 "organization_id": _ORGANIZATION, "cdn_image": "https://cdn.zz/ana.jpg"},
                {"name": "Bo Lin", "label": "Council Member", "source_url": _URL,
                 "organization_id": _ORGANIZATION},
            ]
        },
    )
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id::text FROM source_records WHERE changeset_id = %s AND name = 'Bo Lin'",
            (changeset_id,),
        )
        bo = (await cur.fetchone())[0]
    await _withdraw(EntityType.SOURCE_RECORD, bo, changeset_id)

    [page] = await published_source_pages(_OCDID)

    assert [(r.name, r.cdn_image) for r in page.known_records] == [
        ("Ana Reyes", "https://cdn.zz/ana.jpg")
    ]
