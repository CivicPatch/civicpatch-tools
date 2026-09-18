"""The import reaper: an open sheet import older than the cutoff is dismissed as `expired`.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

from datetime import timedelta

import pytest
import pytest_asyncio

from database.database import get_pool
from database.dismissals import expire_stale_imports
from database.users import SYSTEM_USER_ID
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_reaper/government"
_WEEK = timedelta(days=7)


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM activity WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def _clean():
    await _wipe()
    await factories.seed_jurisdiction(_OCDID, "zz")
    yield
    await _wipe()


async def _changeset(kind: str, days_old: int, published: bool = False) -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO changesets (kind, jurisdiction_ocdid, created_at, published_at)
            VALUES (%s, %s, now() - make_interval(days => %s),
                    CASE WHEN %s THEN now() END)
            RETURNING id::text
            """,
            (kind, _OCDID, days_old, published),
        )
        row = await cur.fetchone()
        await conn.commit()
    assert row
    return row[0]


async def _dismissal(changeset_id: str) -> tuple[str | None, str | None]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT dismissed_reason, resolved_by_user_id::text FROM changesets WHERE id::text = %s",
            (changeset_id,),
        )
        row = await cur.fetchone()
    assert row
    return row[0], row[1]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_import_left_open_past_the_cutoff_expires():
    stale = await _changeset("sheet_import", days_old=8)

    assert await expire_stale_imports(_WEEK) == [stale]
    assert await _dismissal(stale) == ("expired", SYSTEM_USER_ID)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_recent_import_is_left_open():
    fresh = await _changeset("sheet_import", days_old=2)

    assert await expire_stale_imports(_WEEK) == []
    assert await _dismissal(fresh) == (None, None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_only_imports_expire():
    """A scrape waiting as long is still in the review pool, which has its own sweep."""
    scrape = await _changeset("scrape", days_old=30)

    assert await expire_stale_imports(_WEEK) == []
    assert await _dismissal(scrape) == (None, None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_published_import_is_not_expired():
    published = await _changeset("sheet_import", days_old=30, published=True)

    assert await expire_stale_imports(_WEEK) == []
    assert await _dismissal(published) == (None, None)
