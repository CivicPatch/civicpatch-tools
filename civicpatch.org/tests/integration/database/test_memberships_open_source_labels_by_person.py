"""Integration tests for `database.memberships.open_source_labels_by_person` — what `inherit`
resolves against, after identity linking.

Real Postgres, because the join, the default-organization scoping, and the array match are
what's worth checking.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import uuid

import pytest
import pytest_asyncio

from database import divisions, memberships, organizations, posts
from database.database import get_pool

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_inherit/government"
_DIVISION = "ocd-division/country:us/state:zz/place:zz_inherit"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM memberships m USING posts p "
            "WHERE m.post_id = p.id AND p.jurisdiction_ocdid = %s",
            (_OCDID,),
        )
        for table in ("posts", "divisions", "organizations", "people"):
            await cur.execute(f"DELETE FROM {table} WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _seed_open_membership(source_labels: list[str], organization_id: str | None = None) -> str:
    """A currently-held seat. Returns the person id, so a test can look it up by it."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) "
            "VALUES (%s, 'zz', 'local') ON CONFLICT DO NOTHING",
            (_OCDID,),
        )
        person_id = str(uuid.uuid4())
        await cur.execute(
            "INSERT INTO people (id, jurisdiction_ocdid, name) VALUES (%s, %s, %s)",
            (person_id, _OCDID, "Ana Reyes"),
        )
        org = organization_id or await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _DIVISION, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "select-board-chair", _DIVISION)
        await cur.execute(
            """
            INSERT INTO memberships
                (post_id, organization_id, person_id, source_labels, first_seen_at, last_seen_at)
            VALUES (%s, %s, %s, %s, now(), now())
            """,
            (post_id, org, person_id, source_labels),
        )
        await conn.commit()
    return person_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_open_membership_returns_its_source_labels():
    person_id = await _seed_open_membership(["Select Board Chair"])
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        found = await memberships.open_source_labels_by_person(cur, _OCDID, [person_id])
    assert found == {person_id: "Select Board Chair"}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_several_source_labels_join_into_one_reparseable_string():
    person_id = await _seed_open_membership(["Select Board Chair", "Clerk"])
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        found = await memberships.open_source_labels_by_person(cur, _OCDID, [person_id])
    assert found[person_id] == "Select Board Chair / Clerk"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_person_with_no_open_membership_is_absent():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        found = await memberships.open_source_labels_by_person(
            cur, _OCDID, [str(uuid.uuid4())]
        )
    assert found == {}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_empty_person_list_is_not_a_query():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        assert await memberships.open_source_labels_by_person(cur, _OCDID, []) == {}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_membership_in_a_second_organization_is_not_the_default():
    """`inherit` scopes to the earliest-created organization — a jurisdiction that later grows
    a second, named body must not have a membership there picked arbitrarily."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) "
            "VALUES (%s, 'zz', 'local') ON CONFLICT DO NOTHING",
            (_OCDID,),
        )
        first_org = await organizations.find_or_create(cur, _OCDID)
        await cur.execute(
            "INSERT INTO organizations (jurisdiction_ocdid, name, created_at) "
            "VALUES (%s, 'School Board', now() + interval '1 hour') RETURNING id::text",
            (_OCDID,),
        )
        row = await cur.fetchone()
        assert row is not None
        second_org = row[0]
        await conn.commit()

    person_id = await _seed_open_membership(["School Board Member"], organization_id=second_org)

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        found = await memberships.open_source_labels_by_person(cur, _OCDID, [person_id])
    assert found == {}
    assert first_org != second_org
