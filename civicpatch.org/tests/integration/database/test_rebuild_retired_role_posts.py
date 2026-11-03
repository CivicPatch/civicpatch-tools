"""The one-off rebuild for plan 2026-10-30-plan-roles-from-config.md step 3a: a chair still held on
a retired `select-board-chair` post moves to the member post, the empty chair post goes, and a
chair post a claim names stays.

Isolation: sentinel state 'zq', cleaned before and after.
"""

import datetime
import uuid

import pytest
import pytest_asyncio

from database import divisions
from database.database import get_pool
from database.users import SYSTEM_USER_ID
from scripts.rebuild_retired_role_posts import jurisdictions_on_retired_roles, preview, rebuild_and_delete
from core.projection.membership_details import MembershipSource
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zq/place:chairton/government"
_OTHER = "ocd-jurisdiction/country:us/state:zq/place:claimton/government"
_BASE = "ocd-division/country:us/state:zq/place:chairton"
_OTHER_BASE = "ocd-division/country:us/state:zq/place:claimton"
_PAGE = "https://zq.gov/selectboard"
_T0 = datetime.datetime(2026, 6, 2, tzinfo=datetime.timezone.utc)


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        for ocdid in (_OCDID, _OTHER):
            await cur.execute(
                "DELETE FROM memberships m USING posts p WHERE m.post_id = p.id AND p.jurisdiction_ocdid = %s",
                (ocdid,),
            )
            await cur.execute(
                "DELETE FROM claims WHERE entity_type = 'post' AND entity_id IN "
                "(SELECT id FROM posts WHERE jurisdiction_ocdid = %s)",
                (ocdid,),
            )
            await cur.execute("DELETE FROM posts WHERE jurisdiction_ocdid = %s", (ocdid,))
            await cur.execute("DELETE FROM divisions WHERE jurisdiction_ocdid = %s", (ocdid,))
            await cur.execute("DELETE FROM activity WHERE jurisdiction_ocdid = %s", (ocdid,))
            await cur.execute("DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (ocdid,))
            await cur.execute("DELETE FROM organizations WHERE jurisdiction_ocdid = %s", (ocdid,))
            await cur.execute("DELETE FROM people WHERE jurisdiction_ocdid = %s", (ocdid,))
        await cur.execute("DELETE FROM jurisdictions WHERE state = 'zq'")
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _stuck_chair(jurisdiction_ocdid: str, division_ocdid: str) -> tuple[str, str, str]:
    """A town whose chair the old fold put on a `select-board-chair` post, published since only
    as records the new fold reads as a member. Returns (person, organization, chair post)."""
    person_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) VALUES (%s, 'zq', 'local')",
            (jurisdiction_ocdid,),
        )
        organization_id = await factories.default_organization(cur, jurisdiction_ocdid)
        await cur.execute(
            "INSERT INTO people (id, jurisdiction_ocdid, name, urls, source_urls) VALUES (%s, %s, 'Ana', %s, %s)",
            (person_id, jurisdiction_ocdid, [_PAGE], [_PAGE]),
        )
        await conn.commit()
    await factories.published_scrape(
        jurisdiction_ocdid,
        _T0,
        {
            person_id: [
                {
                    "name": "Ana",
                    "label": "Select Board Chair",
                    "source_url": _PAGE,
                    "url": _PAGE,
                    "organization_id": organization_id,
                }
            ]
        },
    )
    async with pool.connection() as conn, conn.cursor() as cur:
        await divisions.find_or_create(cur, division_ocdid, jurisdiction_ocdid)
        chair_post = await factories.seed_post(cur, jurisdiction_ocdid, organization_id, "select-board-chair", division_ocdid)
        await factories.bind_membership(
            cur,
            factories.SeededMembership(
                person_id=person_id, sources=[MembershipSource(note="Select Board Chair", url=_PAGE)]
            ),
            chair_post,
            organization_id,
            _T0,
        )
        await conn.commit()
    return person_id, organization_id, chair_post


async def _claim_post(post_id: str, jurisdiction_ocdid: str) -> None:
    changeset_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO changesets (id, jurisdiction_ocdid, kind, created_at, updated_at, published_at) "
            "VALUES (%s, %s, 'scrape', %s, %s, %s)",
            (changeset_id, jurisdiction_ocdid, _T0, _T0, _T0),
        )
        await cur.execute(
            "INSERT INTO claims (entity_type, entity_id, field_path, kind, value, sources, created_by, created_at, changeset_id) "
            "VALUES ('post', %s, 'tracked', 'accept', 'true'::jsonb, '[{\"note\": \"test\"}]'::jsonb, %s, %s, %s)",
            (post_id, SYSTEM_USER_ID, _T0, changeset_id),
        )
        await conn.commit()


async def _open_posts(person_id: str) -> list[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT p.role_id FROM memberships m JOIN posts p ON p.id = m.post_id "
            "WHERE m.person_id = %s AND m.closed_at IS NULL ORDER BY p.role_id",
            (person_id,),
        )
        return [row[0] for row in await cur.fetchall()]


async def _post_exists(post_id: str) -> bool:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT 1 FROM posts WHERE id = %s", (post_id,))
        return await cur.fetchone() is not None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_stuck_chair_moves_to_the_member_post_and_the_chair_post_goes():
    person_id, _, chair_post = await _stuck_chair(_OCDID, _BASE)
    assert _OCDID in await jurisdictions_on_retired_roles()
    before = await preview(_OCDID)
    assert (before.chairs_moved, before.other_changes) == (1, [])

    await rebuild_and_delete([_OCDID])

    assert await _open_posts(person_id) == ["member"]
    assert not await _post_exists(chair_post)
    assert _OCDID not in await jurisdictions_on_retired_roles()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_chair_post_a_claim_names_is_kept():
    person_id, _, chair_post = await _stuck_chair(_OTHER, _OTHER_BASE)
    await _claim_post(chair_post, _OTHER)

    await rebuild_and_delete([_OTHER])

    assert await _open_posts(person_id) == ["member"]
    assert await _post_exists(chair_post)
