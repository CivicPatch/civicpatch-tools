"""Integration tests for `?as_of` on the posts read.

Real Postgres: the window is a `FILTER` over a partial-index-backed join, and the date
arithmetic (`::date + 1`) is the thing under test.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import json
import uuid
from datetime import date, datetime, timezone

import pytest
import pytest_asyncio

from database import divisions, organizations, posts
from database.database import get_pool

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_asof/government"
_BASE = "ocd-division/country:us/state:zz/place:zz_asof"

_TOOK_OFFICE = datetime(2026, 3, 1, tzinfo=timezone.utc)
_HANDOVER = datetime(2026, 5, 1, tzinfo=timezone.utc)


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM memberships m USING posts p "
            "WHERE m.post_id = p.id AND p.jurisdiction_ocdid = %s",
            (_OCDID,),
        )
        for table in ("posts", "divisions", "organizations", "people"):
            await cur.execute(
                f"DELETE FROM {table} WHERE jurisdiction_ocdid = %s", (_OCDID,)
            )
        await cur.execute(
            "DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _seed_succession() -> str:
    """One seat, two occupants: an outgoing mayor and the one who replaced them.

    Written straight to the table rather than through `record`, because the point is to
    control the observation window — `record` stamps it from the scrape.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) "
            "VALUES (%s, 'zz', 'local')",
            (_OCDID,),
        )
        organization_id = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, organization_id, "mayor", _BASE)

        for name, first_seen_at, closed_at in (
            ("Outgoing", _TOOK_OFFICE, _HANDOVER),
            ("Incoming", _HANDOVER, None),
        ):
            person_id = str(uuid.uuid4())
            await cur.execute(
                "INSERT INTO people (id, jurisdiction_ocdid, data) VALUES (%s, %s, %s)",
                (person_id, _OCDID, json.dumps({"name": name})),
            )
            await cur.execute(
                """
                INSERT INTO memberships
                    (post_id, organization_id, person_id,
                     first_seen_at, last_seen_at, closed_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    post_id,
                    organization_id,
                    person_id,
                    first_seen_at,
                    closed_at or first_seen_at,
                    closed_at,
                ),
            )
        await conn.commit()
    return post_id


async def _holders(as_of: date | None) -> int:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        rows = await posts.list_for_jurisdiction(cur, _OCDID, as_of)
    return rows[0]["holders"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_date_inside_a_closed_window_finds_the_person_who_left():
    """The whole point of keeping closed rows: "who held it then" outlives the tenure."""
    await _seed_succession()

    assert await _holders(date(2026, 4, 1)) == 1
    assert await _holders(date(2026, 6, 1)) == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_seat_never_reads_as_double_occupied_at_the_handover():
    """Both rows touch 2026-05-01 — one closes, one opens. Counting the boundary twice would
    show two mayors on the day the office changed hands."""
    await _seed_succession()

    assert await _holders(date(2026, 5, 1)) == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_today_matches_the_default():
    """The reason a date means end-of-day. At midnight semantics `as_of=today` would drop
    everything observed this morning and silently disagree with the unparameterised read."""
    await _seed_succession()

    assert await _holders(date.today()) == await _holders(None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_before_we_ever_looked_the_seat_is_empty_but_still_there_and_still_vouched_for():
    """Transaction time, so a date before our first scrape has no holders — but the post is
    not a temporal fact and neither is the vouching, and neither may vanish with the clock."""
    await _seed_succession()

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        rows = await posts.list_for_jurisdiction(cur, _OCDID, date(2026, 1, 1))

    assert len(rows) == 1
    assert rows[0]["holders"] == 0
    assert rows[0]["verified"] is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_last_seen_at_does_not_report_from_the_future():
    """A read that reports a sighting later than the date asked about is describing
    observations that had not happened yet.

    NULL is the honest answer when every sighting postdates the query: only the newest
    observation per membership is kept, so the March–May tenure has no April sighting on
    record even though it certainly was observed then.
    """
    await _seed_succession()

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        during = await posts.list_for_jurisdiction(cur, _OCDID, date(2026, 4, 1))
        after = await posts.list_for_jurisdiction(cur, _OCDID, date(2026, 6, 1))

    assert during[0]["last_seen_at"] is None
    assert after[0]["last_seen_at"] == _HANDOVER
