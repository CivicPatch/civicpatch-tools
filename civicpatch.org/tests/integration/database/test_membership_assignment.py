"""Integration tests for seating a person (database.memberships.assign).

Real Postgres: "one open seat per body" is a partial unique index, and the close-then-open is
two statements whose ordering is the guarantee.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import json
import uuid

import pytest
import pytest_asyncio

from database import divisions, memberships, organizations, posts
from database.database import get_pool

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_assign/government"
_BASE = "ocd-division/country:us/state:zz/place:zz_assign"
_WARD_3 = f"{_BASE}/ward:3"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM memberships m USING posts p WHERE m.post_id = p.id AND p.jurisdiction_ocdid = %s",
            (_OCDID,),
        )
        for table in ("posts", "divisions", "organizations", "people"):
            await cur.execute(
                f"DELETE FROM {table} WHERE jurisdiction_ocdid = %s", (_OCDID,)
            )
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _seed() -> tuple[str, str, str]:
    """A person and two posts to move between."""
    person_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) VALUES (%s, 'zz', 'local')",
            (_OCDID,),
        )
        await cur.execute(
            "INSERT INTO people (id, jurisdiction_ocdid, name) "
            "VALUES (%s, %s, %s)",
            (person_id, _OCDID, "Assign Test"),
        )
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        await divisions.find_or_create(cur, _WARD_3, _OCDID)
        first = await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)
        second = await posts.find_or_create(cur, _OCDID, org, "council-member", _WARD_3)
        await conn.commit()
    return person_id, first, second


@pytest.mark.asyncio
@pytest.mark.integration
async def test_assigning_an_unseated_person_reports_no_move():
    person_id, post_id, _ = await _seed()

    result = await memberships.assign(person_id, post_id, "Mayor of Testville")

    assert result["moved_from"] is None
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT label FROM memberships WHERE id::text = %s", (result["membership_id"],)
        )
        assert (await cur.fetchone())[0] == "Mayor of Testville"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_moving_closes_the_old_seat_and_reports_where_from():
    """`moved_from` is what lets the UI say "moved from X" rather than "assigned" — a move
    leaves history behind and the curator should know it did."""
    person_id, first, second = await _seed()
    await memberships.assign(person_id, first, None)

    result = await memberships.assign(person_id, second, None)

    assert result["moved_from"] == first
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT post_id::text, closed_at IS NOT NULL FROM memberships WHERE person_id = %s"
            " ORDER BY first_seen_at",
            (person_id,),
        )
        assert await cur.fetchall() == [(first, True), (second, False)]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_reassigning_to_the_same_seat_only_sets_the_label():
    """Going through `upsert` would overwrite designations with empty arrays, wiping what the
    parser found until the next scrape re-derives it."""
    person_id, post_id, _ = await _seed()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        first = await memberships.upsert(
            cur, person_id, post_id, org, "2026-03-01T00:00:00+00:00",
            designations=["Position 8"],
        )
        await conn.commit()

    result = await memberships.assign(person_id, post_id, "Renamed")

    assert result == {"membership_id": first, "moved_from": None}
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT label, designations FROM memberships WHERE id::text = %s", (first,)
        )
        assert await cur.fetchone() == ("Renamed", ["Position 8"])


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_unknown_post_raises_rather_than_seating_nobody():
    person_id, _, _ = await _seed()

    with pytest.raises(memberships.UnknownPost):
        await memberships.assign(
            person_id, "00000000-0000-0000-0000-000000000000", None
        )
