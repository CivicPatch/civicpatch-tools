"""Integration tests for retracting a membership (`database.memberships.retract`/`restore`)
and its effect on `IS_ON_THE_ROSTER` and `LABEL_IS_HUMAN_SET`.

Against the real DB because both predicates are correlated `EXISTS`/`NOT EXISTS` subqueries
against `assertions`, and the bug this file guards against (a withdrawn assertion still being
read as live) only exists at the SQL level — nothing in Python re-derives it.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import uuid

import pytest
import pytest_asyncio

from core.post_derivation import DerivedMembership
from database import divisions, memberships, organizations, people, posts
from database.database import get_pool

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_retract/government"
_BASE = "ocd-division/country:us/state:zz/place:zz_retract"
_SEEN_AT = "2026-03-11T00:00:00+00:00"
_USER_EMAIL = "zz-retract-user@example.com"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM assertions WHERE entity_id IN "
            "(SELECT m.id FROM memberships m JOIN posts p ON p.id = m.post_id "
            " WHERE p.jurisdiction_ocdid = %s)",
            (_OCDID,),
        )
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
        await cur.execute(
            "DELETE FROM users WHERE provider_user_id = %s", (_USER_EMAIL,)
        )
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _seed() -> tuple[str, str, str, str]:
    """A user, a person, and their one open membership."""
    person_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) "
            "VALUES (%s, 'zz', 'local')",
            (_OCDID,),
        )
        await cur.execute(
            "INSERT INTO users (email, provider, provider_user_id, username, role) "
            "VALUES (%s, 'email', %s, %s, 'admins') RETURNING id::text",
            (_USER_EMAIL, _USER_EMAIL, _USER_EMAIL.replace("@", "-")),
        )
        user_id = (await cur.fetchone())[0]
        await cur.execute(
            "INSERT INTO people (id, jurisdiction_ocdid, name) VALUES (%s, %s, %s)",
            (person_id, _OCDID, "Retract Test"),
        )
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)
        membership_id = await memberships.upsert(
            cur, DerivedMembership(person_id=person_id), post_id, org, _SEEN_AT
        )
        await conn.commit()
    return user_id, person_id, post_id, membership_id


async def _on_roster(person_id: str) -> bool:
    roster = await people.get_roster(_OCDID)
    return any(person["id"] == person_id for person in roster)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_retracting_removes_a_seated_person_from_the_roster():
    user_id, person_id, _, membership_id = await _seed()
    assert await _on_roster(person_id) is True

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await memberships.retract(cur, membership_id, user_id)
        await conn.commit()

    assert await _on_roster(person_id) is False


@pytest.mark.asyncio
@pytest.mark.integration
async def test_retraction_neither_closes_nor_deletes_the_membership():
    """The point of the whole design: unlike `assign` closing a seat, this is reversible — the
    row, its `first_seen_at`, and the post it points at all survive."""
    user_id, _, post_id, membership_id = await _seed()

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await memberships.retract(cur, membership_id, user_id, reason="fabricated by a scrape")
        await conn.commit()

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT closed_at, post_id::text FROM memberships WHERE id::text = %s",
            (membership_id,),
        )
        closed_at, row_post_id = await cur.fetchone()
    assert closed_at is None
    assert row_post_id == post_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_reinstating_returns_them_to_the_roster():
    user_id, person_id, _, membership_id = await _seed()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await memberships.retract(cur, membership_id, user_id)
        await conn.commit()
    assert await _on_roster(person_id) is False

    async with pool.connection() as conn, conn.cursor() as cur:
        reinstated = await memberships.reinstate(cur, membership_id, user_id)
        await conn.commit()

    assert reinstated == 1
    assert await _on_roster(person_id) is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_reinstating_something_not_retracted_does_nothing():
    user_id, _, _, membership_id = await _seed()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        assert await memberships.reinstate(cur, membership_id, user_id) == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_retracting_twice_does_not_accumulate_rows():
    """Same value every time (`_RETRACTED`), so `upsert`'s unchanged-skip applies — retracting
    an already-retracted membership is a no-op, not a second claim."""
    user_id, _, _, membership_id = await _seed()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await memberships.retract(cur, membership_id, user_id)
        await memberships.retract(cur, membership_id, user_id)
        await conn.commit()

        await cur.execute(
            "SELECT count(*) FROM assertions WHERE entity_id::text = %s", (membership_id,)
        )
        assert (await cur.fetchone())[0] == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_withdrawn_label_no_longer_protects_the_field_from_a_scrape():
    """Regression: `LABEL_IS_HUMAN_SET` read the most recent label assertion regardless of
    `withdrawn_at`, so `set_label(..., None, ...)` (clear back to derived) had no effect here —
    the very next scrape was still refused the field it was just supposed to get back."""
    user_id, person_id, post_id, membership_id = await _seed()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)

        await memberships.set_label(cur, membership_id, "Human Label", user_id)
        await conn.commit()

    # A re-scrape of the same seat, proposing a different label.
    async with pool.connection() as conn, conn.cursor() as cur:
        await memberships.upsert(
            cur,
            DerivedMembership(person_id=person_id, label="Scrape Label"),
            post_id,
            org,
            _SEEN_AT,
        )
        await conn.commit()
        await cur.execute(
            "SELECT label FROM memberships WHERE id::text = %s", (membership_id,)
        )
        assert (await cur.fetchone())[0] == "Human Label", "the human's label must still win"

    # Clear it back to derived.
    async with pool.connection() as conn, conn.cursor() as cur:
        await memberships.set_label(cur, membership_id, None, user_id)
        await conn.commit()

    # The next scrape must now be free to set its own label.
    async with pool.connection() as conn, conn.cursor() as cur:
        await memberships.upsert(
            cur,
            DerivedMembership(person_id=person_id, label="Scrape Label 2"),
            post_id,
            org,
            _SEEN_AT,
        )
        await conn.commit()
        await cur.execute(
            "SELECT label FROM memberships WHERE id::text = %s", (membership_id,)
        )
        assert (await cur.fetchone())[0] == "Scrape Label 2"
