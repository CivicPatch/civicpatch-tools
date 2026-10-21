"""Migration 255: posts on the five merged roles move to `president` and `vice-president` with
their people, as a pure rekey. Rows are laid down on the old roles, then 255's own SQL is run
again (it is idempotent, so the test database having applied it once changes nothing).

Isolation: sentinel state 'zp', cleaned before and after.
"""

import datetime
import pathlib
import uuid

import pytest
import pytest_asyncio

from core.projection.facts import PostKey
from database.database import get_pool
from shared.utils.membership_ids import membership_id
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zp/place:presidentville/government"
_PLACE = "ocd-division/country:us/state:zp/place:presidentville"
_WARD = f"{_PLACE}/ward:1"
_T0 = datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc)
_MIGRATION = pathlib.Path(__file__).parents[3] / "database_operations" / "migrations" / "255_president_role.up.sql"
_OLD_ROLES = {
    "council-president": "Council President",
    "village-president": "Village President",
    "commission-president": "Commission President",
    "council-vice-president": "Council Vice President",
    "commissioner-vice-president": "Commissioner Vice President",
}


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM memberships m USING posts p WHERE m.post_id = p.id AND p.jurisdiction_ocdid = %s", (_OCDID,)
        )
        await cur.execute("DELETE FROM posts WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM divisions WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM organizations WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM people WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM jurisdictions WHERE state = 'zp'")
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _seed() -> dict:
    """Ana and Ben on two old president posts at one division (a collision), Cy on a council
    vice president post at ward 1. Ana's post is the older, so it keeps the new key."""
    ids = {name: str(uuid.uuid4()) for name in ("ana", "ben", "cy")}
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        for role_id, label in _OLD_ROLES.items():
            await cur.execute(
                "INSERT INTO roles (id, label, status, is_unique) VALUES (%s, %s, 'inactive', true) ON CONFLICT (id) DO NOTHING",
                (role_id, label),
            )
        await cur.execute("INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) VALUES (%s, 'zp', 'local')", (_OCDID,))
        for division in (_PLACE, _WARD):
            await cur.execute("INSERT INTO divisions (ocdid, jurisdiction_ocdid) VALUES (%s, %s)", (division, _OCDID))
        ids["org"] = await factories.default_organization(cur, _OCDID)
        for name in ("ana", "ben", "cy"):
            await cur.execute("INSERT INTO people (id, jurisdiction_ocdid, name) VALUES (%s, %s, %s)", (ids[name], _OCDID, name.title()))
        seats = [("ana", "council-president", _PLACE), ("ben", "village-president", _PLACE), ("cy", "council-vice-president", _WARD)]
        for minutes, (name, role_id, division) in enumerate(seats):
            post_id = await factories.seed_post(cur, _OCDID, ids["org"], role_id, division)
            await cur.execute("UPDATE posts SET created_at = %s WHERE id = %s", (_T0 + datetime.timedelta(minutes=minutes), post_id))
            await factories.bind_membership(cur, factories.SeededMembership(person_id=ids[name]), post_id, ids["org"], _T0)
        await conn.commit()
    return ids


async def _migrate() -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.set_autocommit(True)
        await conn.execute(_MIGRATION.read_text())  # type: ignore[arg-type]
        await conn.set_autocommit(False)


async def _memberships() -> dict[str, tuple[str, str, str]]:
    """Person id to (membership id, post id, post role)."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT m.person_id::text, m.id::text, p.id::text, p.role_id FROM memberships m JOIN posts p ON p.id = m.post_id "
            "WHERE p.jurisdiction_ocdid = %s",
            (_OCDID,),
        )
        return {person: (membership, post, role) for person, membership, post, role in await cur.fetchall()}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_each_merged_post_moves_to_its_new_role_with_its_people():
    ids = await _seed()

    await _migrate()

    president = PostKey(organization_id=ids["org"], role_id="president", division_ocdid=_PLACE).post_id
    vice = PostKey(organization_id=ids["org"], role_id="vice-president", division_ocdid=_WARD).post_id
    assert await _memberships() == {
        ids["ana"]: (membership_id(ids["ana"], president), president, "president"),
        ids["ben"]: (membership_id(ids["ben"], president), president, "president"),
        ids["cy"]: (membership_id(ids["cy"], vice), vice, "vice-president"),
    }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_two_old_posts_at_one_division_become_one_and_no_old_post_is_left():
    await _seed()

    await _migrate()

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT role_id, count(*) FROM posts WHERE jurisdiction_ocdid = %s GROUP BY 1 ORDER BY 1", (_OCDID,))
        assert await cur.fetchall() == [("president", 1), ("vice-president", 1)]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_organization_keeps_the_oldest_old_roles_word_for_each_new_role():
    ids = await _seed()

    await _migrate()

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT extras_role_labels FROM organizations WHERE id = %s", (ids["org"],))
        row = await cur.fetchone()
    assert row is not None
    assert {k: v for k, v in row[0].items() if k in ("president", "vice-president")} == {
        "president": "Council President",
        "vice-president": "Council Vice President",
    }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_running_it_again_changes_nothing():
    await _seed()
    await _migrate()
    first = await _memberships()

    await _migrate()

    assert await _memberships() == first
    assert len(first) == 3
    assert {role for _, _, role in first.values()} == {"president", "vice-president"}
