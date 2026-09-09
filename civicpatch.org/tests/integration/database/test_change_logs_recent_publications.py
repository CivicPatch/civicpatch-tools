"""Integration test for get_recent_publications' day+jurisdiction grouping.

Real Postgres: the window function + DISTINCT ON collapse several publish_review events on
the same town in one day into a single row, picking the latest author/commit and counting
the rest — this is exactly the part a unit test with a mocked cursor can't exercise honestly.

Run with: mise run tcp-integration
Isolation: sentinel users below, deleted before/after — change_logs cascades on user delete.
"""

from datetime import datetime, timezone

import pytest
import pytest_asyncio

from database.change_logs import get_recent_publications
from database.database import get_pool

_EARLY_EMAIL = "zz-recent-pub-early@example.com"
_LATE_EMAIL = "zz-recent-pub-late@example.com"
_JURISDICTION_OCDID = "ocd-jurisdiction/country:us/state:zz/place:sentineltown/government"

_DAY_ONE_EARLY = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
_DAY_ONE_LATE = datetime(2026, 1, 1, 15, 0, tzinfo=timezone.utc)
_DAY_TWO = datetime(2026, 1, 2, 9, 0, tzinfo=timezone.utc)


async def _wipe():
    """change_logs.user_id is ON DELETE SET NULL, not cascade — deleting the sentinel users
    alone leaves the seeded rows behind (orphaned, but still grouped by the query under test),
    so the jurisdiction has to be cleared explicitly too."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM change_logs WHERE jurisdiction_ocdid = %s", (_JURISDICTION_OCDID,)
        )
        await cur.execute("DELETE FROM users WHERE email IN (%s, %s)", (_EARLY_EMAIL, _LATE_EMAIL))


async def _seed():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        user_ids = {}
        for email in (_EARLY_EMAIL, _LATE_EMAIL):
            await cur.execute(
                "INSERT INTO users (email, provider, provider_user_id, role, display_name) "
                "VALUES (%s, 'email', %s, 'admins', %s) RETURNING id::text",
                (email, email, email),
            )
            row = await cur.fetchone()
            assert row is not None
            user_ids[email] = row[0]

        # Two publish events on the same town, same day — the group get_recent_publications
        # must collapse. A third on the following day stays its own row.
        for user_id, created_at in (
            (user_ids[_EARLY_EMAIL], _DAY_ONE_EARLY),
            (user_ids[_LATE_EMAIL], _DAY_ONE_LATE),
            (user_ids[_EARLY_EMAIL], _DAY_TWO),
        ):
            await cur.execute(
                "INSERT INTO change_logs (type, user_id, jurisdiction_ocdid, created_at) "
                "VALUES ('publish_review', %s, %s, %s)",
                (user_id, _JURISDICTION_OCDID, created_at),
            )


@pytest_asyncio.fixture
async def seeded():
    await _wipe()
    await _seed()
    yield
    await _wipe()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_same_day_same_town_collapses_to_one_row(seeded):
    rows = await get_recent_publications(limit=1000)
    sentinel_rows = [r for r in rows if r["jurisdiction_ocdid"] == _JURISDICTION_OCDID]
    assert len(sentinel_rows) == 2


@pytest.mark.asyncio
@pytest.mark.integration
async def test_collapsed_row_counts_every_review_and_keeps_the_latest(seeded):
    rows = await get_recent_publications(limit=1000)
    day_one = next(
        r
        for r in rows
        if r["jurisdiction_ocdid"] == _JURISDICTION_OCDID
        and r["created_at"].date() == _DAY_ONE_LATE.date()
    )
    assert day_one["review_count"] == 2
    assert day_one["author_name"] == _LATE_EMAIL
    assert day_one["created_at"] == _DAY_ONE_LATE


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_next_day_stays_its_own_row(seeded):
    rows = await get_recent_publications(limit=1000)
    day_two = next(
        r
        for r in rows
        if r["jurisdiction_ocdid"] == _JURISDICTION_OCDID and r["created_at"] == _DAY_TWO
    )
    assert day_two["review_count"] == 1
