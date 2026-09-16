"""Which organization is a jurisdiction's default, and how it survives renames.

Isolation: sentinel state 'zz', place `zz_orgs_db`, cleaned before and after each test.
"""

import psycopg
import pytest
import pytest_asyncio

from database import organizations
from database.database import get_pool

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_orgs_db/government"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM organizations WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def sentinel_jurisdiction():
    await _wipe()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) VALUES (%s, 'zz', 'local')",
            (_OCDID,),
        )
        await conn.commit()
    yield
    await _wipe()


async def _insert(name: str, sort_order: int = 0, is_default: bool = False) -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO organizations (jurisdiction_ocdid, name, sort_order, meta_is_default)
            VALUES (%s, %s, %s, %s)
            RETURNING id::text
            """,
            (_OCDID, name, sort_order, is_default),
        )
        row = await cur.fetchone()
        await conn.commit()
    assert row is not None
    return row[0]


async def _default() -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        return await organizations.get_default(cur, _OCDID)


async def _names() -> list[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT name FROM organizations WHERE jurisdiction_ocdid = %s ORDER BY name", (_OCDID,)
        )
        return [row[0] for row in await cur.fetchall()]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_flagged_organization_is_the_default_wherever_it_sorts():
    await _insert("City Council", sort_order=0)
    mayor = await _insert("Office of the Mayor", sort_order=5, is_default=True)

    assert await _default() == mayor


@pytest.mark.asyncio
@pytest.mark.integration
async def test_without_a_flag_the_first_in_list_order_is_the_default():
    await _insert("Government", sort_order=1)
    first = await _insert("School Board", sort_order=0)

    assert await _default() == first


@pytest.mark.asyncio
@pytest.mark.integration
async def test_renaming_the_default_keeps_it_the_default():
    default = await _insert("Government", is_default=True)
    await organizations.update(default, "City Council", None)

    assert await _default() == default


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_jurisdiction_with_no_organizations_is_an_error_not_a_guess():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        with pytest.raises(RuntimeError):
            await organizations.get_default(cur, _OCDID)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_jurisdiction_cannot_have_two_defaults():
    await _insert("Government", is_default=True)

    with pytest.raises(psycopg.errors.UniqueViolation):
        await _insert("City Council", is_default=True)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_ensure_defaults_exist_creates_a_flagged_first_organization():
    await organizations.ensure_defaults_exist([_OCDID])

    created = await _default()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT name, meta_is_default FROM organizations WHERE id = %s", (created,)
        )
        assert await cur.fetchone() == (organizations.DEFAULT_ORGANIZATION_NAME, True)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_ensure_defaults_exist_does_not_recreate_a_renamed_default():
    await organizations.ensure_defaults_exist([_OCDID])
    await organizations.update(await _default(), "City Council", None)

    await organizations.ensure_defaults_exist([_OCDID])

    assert await _names() == ["City Council"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_default_cannot_be_deleted_even_after_a_rename():
    default = await _insert("Government", is_default=True)
    await organizations.update(default, "City Council", None)

    assert await organizations.delete(default) is None
    assert await _names() == ["City Council"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_setting_a_default_moves_the_flag_off_the_old_one():
    government = await _insert("Government", is_default=True)
    mayor = await _insert("Office of the Mayor")

    assert await organizations.set_default(mayor) is True

    assert await _default() == mayor
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT meta_is_default FROM organizations WHERE id = %s", (government,)
        )
        assert await cur.fetchone() == (False,)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_setting_the_current_default_again_changes_nothing():
    government = await _insert("Government", is_default=True)

    assert await organizations.set_default(government) is True
    assert await _default() == government


@pytest.mark.asyncio
@pytest.mark.integration
async def test_setting_a_missing_organization_as_default_is_false():
    assert await organizations.set_default("00000000-0000-0000-0000-000000000000") is False


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_non_default_organization_can_be_deleted():
    await _insert("Government", is_default=True)
    board = await _insert("School Board")

    assert await organizations.delete(board) == _OCDID
    assert await _names() == ["Government"]
