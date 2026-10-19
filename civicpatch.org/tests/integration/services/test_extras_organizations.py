"""Saving a jurisdiction's `extras_organizations`: written over what was there, read back as the
model, refused for a role the config lacks, and logged as an edit of the jurisdiction."""

import json

import pytest
import pytest_asyncio

from database.database import get_pool
from services.extras_organizations import UnknownJurisdiction, UnknownRole, get_extras_organizations, set_extras_organizations
from shared.schemas import GoverningLawOrganizations

_TOWN = "ocd-jurisdiction/country:us/state:vt/place:zyorg_town/government"
_UNKNOWN = "ocd-jurisdiction/country:us/state:vt/place:zyorg_nowhere/government"
_ROLE = "zz-test-trustee"


def _organizations(role: str, maximum_memberships: int = 5) -> GoverningLawOrganizations:
    return GoverningLawOrganizations.model_validate({
        "organizations": [{
            "name": "Board of Trustees",
            "posts": [{
                "role": role,
                "maximum_memberships": maximum_memberships,
                "extras": {"selection_method": "elected_by_voters"},
                "sources": [{"url": "https://example.gov/24/039", "note": "five trustees", "extras": {"source_page_id": "p1"}}],
            }],
        }],
        "extras": {"governing_law_collected_at": "2026-10-19T00:00:00Z"},
    })


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM activity WHERE jurisdiction_ocdid = %s", (_TOWN,))
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_TOWN,))
        await cur.execute("DELETE FROM roles WHERE id = %s", (_ROLE,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def _seeded():
    await _wipe()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, data, updated_at) VALUES (%s, 'vt', %s, now())",
            (_TOWN, json.dumps({"name": "Zyorg town"})),
        )
        await cur.execute("INSERT INTO roles (id, label, status) VALUES (%s, 'ZZ Test Trustee', 'active')", (_ROLE,))
        await conn.commit()
    yield
    await _wipe()


async def _edited_fields() -> list[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT changes FROM activity WHERE jurisdiction_ocdid = %s AND type = 'edit_jurisdiction' ORDER BY created_at",
            (_TOWN,),
        )
        return [field["field"] for (changes,) in await cur.fetchall() for field in changes["fields"]]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_nothing_until_the_collector_has_written_it():
    assert await get_extras_organizations(_TOWN) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_written_over_what_was_there_and_logged():
    await set_extras_organizations(_TOWN, _organizations(_ROLE, maximum_memberships=3), None)
    await set_extras_organizations(_TOWN, _organizations(_ROLE), None)

    assert await get_extras_organizations(_TOWN) == _organizations(_ROLE)
    assert await _edited_fields() == ["extras_organizations", "extras_organizations"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_role_the_config_lacks_is_refused():
    with pytest.raises(UnknownRole, match="collector-of-taxes"):
        await set_extras_organizations(_TOWN, _organizations("collector-of-taxes"), None)

    assert await get_extras_organizations(_TOWN) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_an_unknown_jurisdiction_is_refused():
    with pytest.raises(UnknownJurisdiction):
        await set_extras_organizations(_UNKNOWN, _organizations(_ROLE), None)
