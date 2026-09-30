"""Integration tests for `source_pages` (database.source_pages).

Against the real test DB: the uuid[] cast, the nullable changeset, and the one-row-per-page-per-run
key are the things a mock cannot show.

Isolation: every row hangs off one sentinel jurisdiction, removed before and after each test.
"""
import uuid

import pytest
import pytest_asyncio

from core.source_pages import SourcePageRow
from database.database import get_pool
from database.source_pages import insert_source_pages

_SENTINEL_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_source_pages/government"
_ORGANIZATION = "00000000-0000-4000-8000-0000000000c1"


async def _cleanup():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        # source_pages cascades from both.
        await cur.execute("DELETE FROM pipeline_runs WHERE jurisdiction_ocdid = %s", (_SENTINEL_OCDID,))
        await cur.execute("DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_SENTINEL_OCDID,))
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_SENTINEL_OCDID,))
        await conn.commit()


@pytest_asyncio.fixture
async def sentinel_run():
    await _cleanup()
    run_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("INSERT INTO jurisdictions (jurisdiction_ocdid) VALUES (%s)", (_SENTINEL_OCDID,))
        await cur.execute(
            "INSERT INTO changesets (kind, jurisdiction_ocdid) VALUES ('scrape', %s) RETURNING id::text",
            (_SENTINEL_OCDID,),
        )
        changeset_id = (await cur.fetchone())[0]
        await cur.execute(
            "INSERT INTO pipeline_runs (id, jurisdiction_ocdid, arguments_json) VALUES (%s, %s, '{}')",
            (run_id, _SENTINEL_OCDID),
        )
        await conn.commit()
    yield run_id, changeset_id
    await _cleanup()


def _row(run_id: str, changeset_id: str | None, url: str = "https://zz.gov/council") -> SourcePageRow:
    return SourcePageRow(
        source_url=url,
        jurisdiction_ocdid=_SENTINEL_OCDID,
        pipeline_run_id=run_id,
        changeset_id=changeset_id,
        organization_ids=[_ORGANIZATION],
        page_hash="p",
        prompt_hash="q",
        cache_path=f"{run_id}/data_source/zz/local/place_zz/cache/council",
        anchor_text="City Council",
        is_relevant=True,
        relevant_urls=["https://zz.gov/mayor"],
        heuristics_failures=["name_not_in_text"],
    )


async def _stored(run_id: str) -> list[tuple]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT source_url, changeset_id::text, organization_ids::text[], heuristics_failures
            FROM source_pages WHERE pipeline_run_id = %s ORDER BY source_url
            """,
            (run_id,),
        )
        return await cur.fetchall()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_page_is_stored_with_its_organizations(sentinel_run):
    run_id, changeset_id = sentinel_run

    assert await insert_source_pages([_row(run_id, changeset_id)]) == 1

    assert await _stored(run_id) == [
        ("https://zz.gov/council", changeset_id, [_ORGANIZATION], ["name_not_in_text"])
    ]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_retried_submit_writes_nothing_twice(sentinel_run):
    run_id, changeset_id = sentinel_run

    await insert_source_pages([_row(run_id, changeset_id)])
    await insert_source_pages([_row(run_id, changeset_id)])

    assert len(await _stored(run_id)) == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_failed_run_stores_its_pages_with_no_changeset(sentinel_run):
    run_id, _ = sentinel_run

    await insert_source_pages([_row(run_id, None)])

    [(_, changeset_id, _, _)] = await _stored(run_id)
    assert changeset_id is None
