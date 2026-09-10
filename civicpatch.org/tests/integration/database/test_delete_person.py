"""Integration tests for `database.people.delete_person`.

Real Postgres because what's under test is that the mint (`register_people_edit_changeset`,
which resolves `parent_changeset_id` and inserts against real FKs) and the delete land
correctly together — a mocked cursor couldn't catch the FK/timing details this touches.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import uuid

import pytest
import pytest_asyncio

from database.database import get_pool
from database.people import delete_person

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_delete_person/government"
_USER_EMAIL = "zz-delete-person@example.com"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM activity WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await cur.execute(
            "DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await cur.execute("DELETE FROM people WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute(
            "DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await cur.execute(
            "DELETE FROM users WHERE provider_user_id = %s", (_USER_EMAIL,)
        )
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _seed_person() -> tuple[str, str]:
    """A jurisdiction, a user, and a person in it. Returns (user_id, person_id)."""
    person_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) "
            "VALUES (%s, 'zz', 'local')",
            (_OCDID,),
        )
        await cur.execute(
            "INSERT INTO users (email, provider, provider_user_id, role) "
            "VALUES (%s, 'email', %s, 'admins') RETURNING id::text",
            (_USER_EMAIL, _USER_EMAIL),
        )
        row = await cur.fetchone()
        assert row is not None
        user_id = row[0]
        await cur.execute(
            "INSERT INTO people (id, jurisdiction_ocdid, name) VALUES (%s, %s, %s)",
            (person_id, _OCDID, "Delete Test"),
        )
        await conn.commit()
    return user_id, person_id


async def test_deleting_mints_a_born_published_changeset():
    user_id, person_id = await _seed_person()

    returned_ocdid = await delete_person(person_id, user_id)

    assert returned_ocdid == _OCDID
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT kind, jurisdiction_ocdid, published_at, created_by_user_id "
            "FROM changesets WHERE jurisdiction_ocdid = %s",
            (_OCDID,),
        )
        rows = await cur.fetchall()

    assert len(rows) == 1
    kind, jurisdiction_ocdid, published_at, created_by_user_id = rows[0]
    assert kind == "people_edit"
    assert jurisdiction_ocdid == _OCDID
    assert published_at is not None, "born published — no review phase for a deletion"
    assert str(created_by_user_id) == user_id


async def test_the_activity_row_references_the_minted_changeset():
    user_id, person_id = await _seed_person()

    await delete_person(person_id, user_id)

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT changeset_id::text FROM activity "
            "WHERE type = 'delete_person' AND jurisdiction_ocdid = %s",
            (_OCDID,),
        )
        activity_row = await cur.fetchone()
        assert activity_row is not None
        activity_changeset_id = activity_row[0]

        await cur.execute(
            "SELECT id::text FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        changeset_row = await cur.fetchone()
        assert changeset_row is not None

    assert activity_changeset_id == changeset_row[0]


async def test_deleting_removes_the_person_row():
    user_id, person_id = await _seed_person()

    await delete_person(person_id, user_id)

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT 1 FROM people WHERE id = %s", (person_id,))
        assert await cur.fetchone() is None


async def test_deleting_someone_who_does_not_exist_returns_none():
    assert await delete_person(str(uuid.uuid4()), str(uuid.uuid4())) is None
