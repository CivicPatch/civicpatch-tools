"""Migration 264: a post with no label gets its organization's, else its role's, and running it again
changes nothing, though the function it replaces is gone by then.

Isolation: sentinel state 'zy', cleaned before and after.
"""

import pathlib

import pytest
import pytest_asyncio

from database.database import get_pool
from database.divisions import find_or_create
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zy/place:labelville/government"
_PLACE = "ocd-division/country:us/state:zy/place:labelville"
_MIGRATION = (
    pathlib.Path(__file__).parents[3] / "database_operations" / "migrations" / "264_posts_role_label.up.sql"
)


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM posts WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM divisions WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM organizations WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM jurisdictions WHERE state = 'zy'")
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _seed_unlabelled_posts() -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) VALUES (%s, 'zy', 'local')", (_OCDID,)
        )
        organization_id = await factories.default_organization(cur, _OCDID)
        await cur.execute(
            """UPDATE organizations SET extras_role_labels = '{"member": "Select Board Member"}'::jsonb WHERE id = %s""",
            (organization_id,),
        )
        await find_or_create(cur, _PLACE, _OCDID)
        await factories.seed_post(cur, _OCDID, organization_id, "member", _PLACE)
        await factories.seed_post(cur, _OCDID, organization_id, "mayor", _PLACE)
        await cur.execute("UPDATE posts SET role_label = NULL WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await conn.commit()


async def _migrate() -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.set_autocommit(True)
        await conn.execute(_MIGRATION.read_text())  # type: ignore[arg-type]
        await conn.set_autocommit(False)


async def _labels() -> dict[str, str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT role_id, role_label FROM posts WHERE jurisdiction_ocdid = %s", (_OCDID,))
        return {row[0]: row[1] for row in await cur.fetchall()}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_post_with_no_label_gets_its_organizations_else_its_roles():
    await _seed_unlabelled_posts()

    await _migrate()

    assert await _labels() == {"member": "Select Board Member", "mayor": "Mayor"}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_running_it_again_changes_nothing():
    await _seed_unlabelled_posts()
    await _migrate()

    await _migrate()

    assert await _labels() == {"member": "Select Board Member", "mayor": "Mayor"}
