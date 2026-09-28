"""`resolved_government_form` against real jurisdiction rows: its government form wins, then
the shipped config, and a state or an unknown jurisdiction resolves to nothing.

The config is the real `government_forms.yml`, so a rule edited there can move these cases.
"""

import json

import pytest
import pytest_asyncio

from database.database import get_pool
from database.organizations import ensure_defaults_exist
from services.government_form import (
    ensure_government_form_organizations,
    resolved_government_form,
)
from shared.schemas import GovernmentForm

_MI_TOWNSHIP = "ocd-jurisdiction/country:us/state:mi/place:zyform_township/government"
_WA_CITY = "ocd-jurisdiction/country:us/state:wa/place:zyform_city/government"
_WA_STATE = "ocd-jurisdiction/country:us/state:wa/government"
_UNKNOWN = "ocd-jurisdiction/country:us/state:wa/place:zyform_missing/government"
_MA_TOWN = "ocd-jurisdiction/country:us/state:ma/place:zyform_town/government"


async def _seed(
    jurisdiction_ocdid: str, state: str, data: dict, government_form: str | None = None
) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO jurisdictions
                (jurisdiction_ocdid, state, data, meta_government_form, updated_at)
            VALUES (%s, %s, %s::jsonb, %s, now())
            ON CONFLICT (jurisdiction_ocdid) DO UPDATE
                SET data = EXCLUDED.data, meta_government_form = EXCLUDED.meta_government_form
            """,
            (jurisdiction_ocdid, state, json.dumps(data), government_form),
        )
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def _cleanup():
    yield
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        seeded = [_MI_TOWNSHIP, _WA_CITY, _MA_TOWN]
        await cur.execute("DELETE FROM activity WHERE jurisdiction_ocdid = ANY(%s)", (seeded,))
        await cur.execute("DELETE FROM organizations WHERE jurisdiction_ocdid = ANY(%s)", (seeded,))
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = ANY(%s)", (seeded,))
        await conn.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_config_rule_decides_a_michigan_township():
    await _seed(_MI_TOWNSHIP, "mi", {"name": "Zyform township"})

    assert await resolved_government_form(_MI_TOWNSHIP) == GovernmentForm.TOWNSHIP_BOARD


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_government_form_beats_the_config_rule():
    await _seed(_MI_TOWNSHIP, "mi", {"name": "Zyform township"}, government_form="mayor_council")

    assert await resolved_government_form(_MI_TOWNSHIP) == GovernmentForm.MAYOR_COUNCIL


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_city_the_config_leaves_open_resolves_to_nothing():
    await _seed(_WA_CITY, "wa", {"name": "Zyform city"})

    assert await resolved_government_form(_WA_CITY) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_state_resolves_to_nothing():
    assert await resolved_government_form(_WA_STATE) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_an_unknown_jurisdiction_resolves_to_nothing():
    assert await resolved_government_form(_UNKNOWN) is None


async def _organizations(jurisdiction_ocdid: str) -> list[tuple[str, str, bool]]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id::text, name, meta_is_default FROM organizations
            WHERE jurisdiction_ocdid = %s ORDER BY meta_is_default DESC, name
            """,
            (jurisdiction_ocdid,),
        )
        return list(await cur.fetchall())


async def _saved_form(jurisdiction_ocdid: str) -> str | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT meta_government_form FROM jurisdictions WHERE jurisdiction_ocdid = %s",
            (jurisdiction_ocdid,),
        )
        row = await cur.fetchone()
        return row[0] if row else None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_applying_a_rule_decided_form_renames_the_default_and_saves_the_form():
    await _seed(_MI_TOWNSHIP, "mi", {"name": "Zyform township"})
    await ensure_defaults_exist([_MI_TOWNSHIP])
    [(default_id, _, _)] = await _organizations(_MI_TOWNSHIP)

    await ensure_government_form_organizations()

    assert await _organizations(_MI_TOWNSHIP) == [(default_id, "Board", True)]
    assert await _saved_form(_MI_TOWNSHIP) == "township_board"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_saved_form_creates_the_second_organization_beside_the_renamed_default():
    await _seed(_MA_TOWN, "ma", {"name": "Zyform town"}, government_form="open_town_meeting")
    await ensure_defaults_exist([_MA_TOWN])
    [(default_id, _, _)] = await _organizations(_MA_TOWN)

    await ensure_government_form_organizations()

    organizations = await _organizations(_MA_TOWN)
    assert organizations[0] == (default_id, "Select Board", True)
    assert [(name, is_default) for _, name, is_default in organizations[1:]] == [
        ("Town Meeting", False)
    ]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_applying_a_form_twice_changes_nothing_the_second_time():
    await _seed(_MI_TOWNSHIP, "mi", {"name": "Zyform township"})
    await ensure_defaults_exist([_MI_TOWNSHIP])
    await ensure_government_form_organizations()
    before = await _organizations(_MI_TOWNSHIP)

    await ensure_government_form_organizations()

    assert await _organizations(_MI_TOWNSHIP) == before


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_jurisdiction_the_config_leaves_open_is_not_touched():
    await _seed(_WA_CITY, "wa", {"name": "Zyform city"})
    await ensure_defaults_exist([_WA_CITY])

    await ensure_government_form_organizations()

    assert [name for _, name, _ in await _organizations(_WA_CITY)] == ["Government"]
    assert await _saved_form(_WA_CITY) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_sync_pass_applies_forms_not_yet_applied_and_leaves_open_ones_alone():
    await _seed(_MI_TOWNSHIP, "mi", {"name": "Zyform township"})
    await _seed(_WA_CITY, "wa", {"name": "Zyform city"})
    await ensure_defaults_exist([_MI_TOWNSHIP, _WA_CITY])

    await ensure_government_form_organizations()

    assert [name for _, name, _ in await _organizations(_MI_TOWNSHIP)] == ["Board"]
    assert await _saved_form(_MI_TOWNSHIP) == "township_board"
    assert [name for _, name, _ in await _organizations(_WA_CITY)] == ["Government"]
    assert await _saved_form(_WA_CITY) is None
