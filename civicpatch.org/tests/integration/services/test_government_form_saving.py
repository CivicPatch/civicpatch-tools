"""Saving a jurisdiction's government form: a person or the service key replaces it, and either
builds the organizations it implies. Also whether a scrape is asked for it at all."""

import json

import pytest
import pytest_asyncio

from database.database import get_pool
from database.organizations import ensure_defaults_exist
from database.users import SYSTEM_USER_ID
from services.government_form import (
    GovernmentFormNotAtLevel,
    government_form_choices,
    resolved_government,
    set_government_form,
)
from shared.schemas import GovernmentForm
from shared.utils.government_forms import DerivedOrganization
from shared.utils.layered_config import COUNTRY_ROLES_PATH, ConfigFile, ConfigRole, GovernmentFormConfig

_CITY = "ocd-jurisdiction/country:us/state:wa/place:zysave_city/government"

_CONFIGS = {
    COUNTRY_ROLES_PATH: ConfigFile(
        roles=[ConfigRole(id="mayor", label="Mayor"), ConfigRole(id="council-member", label="Council Member")]
    ),
    "data_source/local/config.yml": ConfigFile(
        government_forms={
            GovernmentForm.MAYOR_COUNCIL: GovernmentFormConfig(
                organizations=[
                    DerivedOrganization(name="Council", role_labels=["Council Member"]),
                    DerivedOrganization(name="Office of the Mayor", role_labels=["Mayor"]),
                ]
            ),
            GovernmentForm.COUNCIL_MANAGER: GovernmentFormConfig(
                organizations=[DerivedOrganization(name="Council", role_labels=["Council Member", "Mayor"])]
            ),
        }
    ),
}


@pytest_asyncio.fixture(autouse=True)
async def _seeded():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        for path, config in _CONFIGS.items():
            await cur.execute(
                """
                INSERT INTO jurisdiction_configs (path, content, commit_sha) VALUES (%s, %s, 'test')
                ON CONFLICT (path) DO UPDATE SET content = EXCLUDED.content
                """,
                (path, config.model_dump_json()),
            )
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, data, updated_at) VALUES (%s, 'wa', %s, now())",
            (_CITY, json.dumps({"name": "Zysave city"})),
        )
        await conn.commit()
    await ensure_defaults_exist([_CITY])
    yield
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM activity WHERE jurisdiction_ocdid = %s", (_CITY,))
        await cur.execute("DELETE FROM organizations WHERE jurisdiction_ocdid = %s", (_CITY,))
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_CITY,))
        await cur.execute("DELETE FROM jurisdiction_configs WHERE path = ANY(%s)", (list(_CONFIGS),))
        await conn.commit()


async def _organization_names() -> list[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT name FROM organizations WHERE jurisdiction_ocdid = %s ORDER BY meta_is_default DESC, name",
            (_CITY,),
        )
        return [row[0] for row in await cur.fetchall()]


async def _logged_fields() -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT changes->'fields' FROM activity WHERE jurisdiction_ocdid = %s ORDER BY created_at",
            (_CITY,),
        )
        return [row[0] for row in await cur.fetchall()]


async def _saved_form() -> GovernmentForm | None:
    return (await resolved_government(_CITY)).government_form


@pytest.mark.integration
@pytest.mark.asyncio
async def test_setting_the_form_saves_it_logs_it_and_builds_its_organizations():
    await set_government_form(_CITY, GovernmentForm.MAYOR_COUNCIL, SYSTEM_USER_ID)

    assert await _saved_form() == GovernmentForm.MAYOR_COUNCIL
    assert await _organization_names() == ["City Officers", "Council", "Office of the Mayor"]
    assert [{"field": "government_form", "before": None, "after": "mayor_council", "sources": []}] in (
        await _logged_fields()
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_person_overwrites_a_saved_form():
    await set_government_form(_CITY, GovernmentForm.COUNCIL_MANAGER, SYSTEM_USER_ID)

    await set_government_form(_CITY, GovernmentForm.MAYOR_COUNCIL, SYSTEM_USER_ID)

    assert await _saved_form() == GovernmentForm.MAYOR_COUNCIL


@pytest.mark.integration
@pytest.mark.asyncio
async def test_changing_the_form_adds_its_organizations_and_removes_none():
    await set_government_form(_CITY, GovernmentForm.MAYOR_COUNCIL, SYSTEM_USER_ID)

    await set_government_form(_CITY, GovernmentForm.COUNCIL_MANAGER, SYSTEM_USER_ID)

    assert await _organization_names() == ["City Officers", "Council", "Office of the Mayor"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_service_key_saves_like_anyone():
    await set_government_form(_CITY, GovernmentForm.COUNCIL_MANAGER, SYSTEM_USER_ID)

    await set_government_form(_CITY, GovernmentForm.MAYOR_COUNCIL, None)

    assert await _saved_form() == GovernmentForm.MAYOR_COUNCIL


@pytest.mark.integration
@pytest.mark.asyncio
async def test_an_undecided_jurisdiction_is_offered_every_allowed_form():
    assert await government_form_choices(_CITY) == [GovernmentForm.MAYOR_COUNCIL, GovernmentForm.COUNCIL_MANAGER]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_no_choices_once_the_form_is_set():
    await set_government_form(_CITY, GovernmentForm.MAYOR_COUNCIL, SYSTEM_USER_ID)

    assert await government_form_choices(_CITY) == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_form_from_another_level_is_refused():
    with pytest.raises(GovernmentFormNotAtLevel):
        await set_government_form(_CITY, GovernmentForm.COUNTY_EXECUTIVE, SYSTEM_USER_ID)

    assert await _saved_form() is None
