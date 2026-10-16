"""Open work that blocks a scrape and reads as "needs review": only a scrape with records.

Isolation: sentinel state 'zw', so another suite's fixtures cannot leak in.
"""

import uuid

import pytest
import pytest_asyncio

from database.database import get_pool
from database.review_pool import has_open_review, jurisdiction_ocdids_with_open_changesets
from database.source_records import insert_source_records
from tests.integration import factories

_WITH_RECORDS = "ocd-jurisdiction/country:us/state:zw/place:zyrecords/government"
_EMPTY = "ocd-jurisdiction/country:us/state:zw/place:zyempty/government"


@pytest_asyncio.fixture(autouse=True)
async def _clean():
    yield
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        sentinels = [_WITH_RECORDS, _EMPTY]
        await cur.execute("DELETE FROM source_records WHERE jurisdiction_ocdid = ANY(%s)", (sentinels,))
        await cur.execute("DELETE FROM pipeline_runs WHERE jurisdiction_ocdid = ANY(%s)", (sentinels,))
        await cur.execute("DELETE FROM changesets WHERE jurisdiction_ocdid = ANY(%s)", (sentinels,))
        await cur.execute("DELETE FROM organizations WHERE jurisdiction_ocdid = ANY(%s)", (sentinels,))
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = ANY(%s)", (sentinels,))
        await conn.commit()


async def _open_scrape(jurisdiction_ocdid: str, *, with_records: bool) -> None:
    await factories.seed_jurisdiction(jurisdiction_ocdid, "zw")
    changeset_id = await factories.complete_run(await factories.start_run(jurisdiction_ocdid))
    if not with_records:
        return
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_id = await factories.default_organization(cur, jurisdiction_ocdid)
        await conn.commit()
    await insert_source_records(
        changeset_id,
        jurisdiction_ocdid,
        {
            str(uuid.uuid4()): [
                {
                    "name": "Ana Reyes",
                    "label": "Mayor",
                    "source_url": "https://zy.gov/council",
                    "organization_id": organization_id,
                }
            ]
        },
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_an_open_scrape_that_kept_no_records_is_not_open_work():
    """It shows on no review surface, so it must not block a scrape or read as needing review."""
    await _open_scrape(_WITH_RECORDS, with_records=True)
    await _open_scrape(_EMPTY, with_records=False)

    assert await jurisdiction_ocdids_with_open_changesets("zw") == {_WITH_RECORDS}
    assert await has_open_review(_WITH_RECORDS)
    assert not await has_open_review(_EMPTY)
