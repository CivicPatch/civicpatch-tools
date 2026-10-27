"""Migration 259: every default organization becomes `{lsad} Officers`. One still named
"Government" is renamed in place; one renamed to a board before keeps its name and the flag
moves to a new Officers organization beside it. 259's own SQL is run (idempotent, so the test
database having applied it once changes nothing).

Isolation: sentinel state 'zo', cleaned before and after.
"""

import json
import pathlib

import pytest
import pytest_asyncio

from database.database import get_pool

_UNTOUCHED = "ocd-jurisdiction/country:us/state:zo/place:zyuntouched/government"
_RENAMED = "ocd-jurisdiction/country:us/state:zo/place:zyrenamed/government"
_MIGRATION = (
    pathlib.Path(__file__).parents[3] / "database_operations" / "migrations"
    / "259_default_organization_is_officers.up.sql"
)


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM organizations WHERE jurisdiction_ocdid IN (%s, %s)", (_UNTOUCHED, _RENAMED))
        await cur.execute("DELETE FROM jurisdictions WHERE state = 'zo'")
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _seed() -> dict[str, str]:
    """Two towns: one whose default is still "Government", one whose default was renamed to
    "Select Board" beside a "Town Meeting". Returns each default's id."""
    pool = await get_pool()
    ids = {}
    async with pool.connection() as conn, conn.cursor() as cur:
        for ocdid, default_name in ((_UNTOUCHED, "Government"), (_RENAMED, "Select Board")):
            await cur.execute(
                "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level, data) VALUES (%s, 'zo', 'local', %s::jsonb)",
                (ocdid, json.dumps({"name": "Zyofficers town"})),
            )
            await cur.execute(
                "INSERT INTO organizations (jurisdiction_ocdid, name, meta_is_default) VALUES (%s, %s, true) RETURNING id::text",
                (ocdid, default_name),
            )
            row = await cur.fetchone()
            assert row is not None
            ids[ocdid] = row[0]
        await cur.execute(
            "INSERT INTO organizations (jurisdiction_ocdid, name) VALUES (%s, 'Town Meeting')", (_RENAMED,)
        )
        await conn.commit()
    return ids


async def _migrate() -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.set_autocommit(True)
        await conn.execute(_MIGRATION.read_text())  # type: ignore[arg-type]
        await conn.set_autocommit(False)


async def _organizations(jurisdiction_ocdid: str) -> list[tuple[str, str, bool]]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id::text, name, meta_is_default FROM organizations WHERE jurisdiction_ocdid = %s ORDER BY name",
            (jurisdiction_ocdid,),
        )
        return list(await cur.fetchall())


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_default_still_named_government_is_renamed_in_place():
    ids = await _seed()

    await _migrate()

    assert await _organizations(_UNTOUCHED) == [(ids[_UNTOUCHED], "Town Officers", True)]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_default_renamed_before_keeps_its_name_and_officers_take_the_flag():
    ids = await _seed()

    await _migrate()

    organizations = await _organizations(_RENAMED)
    assert [(name, is_default) for _, name, is_default in organizations] == [
        ("Select Board", False),
        ("Town Meeting", False),
        ("Town Officers", True),
    ]
    assert organizations[0][0] == ids[_RENAMED]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_running_it_again_changes_nothing():
    await _seed()
    await _migrate()
    before = (await _organizations(_UNTOUCHED), await _organizations(_RENAMED))

    await _migrate()

    assert (await _organizations(_UNTOUCHED), await _organizations(_RENAMED)) == before
