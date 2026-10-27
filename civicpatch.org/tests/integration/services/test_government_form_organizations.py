"""A merged config file gives the jurisdictions it governs their organizations: created where
missing, labelled where unlabelled, a person's own left alone; a second application changes
nothing. The config is stored the way the merge Action's sync stores it.

Isolation: state 'zz', sentinel roles `zz-test-*`, the config path for 'zz' local, cleaned
before and after.
"""

import json

import pytest
import pytest_asyncio

import database.jurisdiction_configs as jurisdiction_configs_db
import services.government_form as government_form_service
from database.database import get_pool
from schemas.jurisdiction_configs import JurisdictionConfigVersion
from shared.schemas import GovernmentForm
from shared.utils.government_forms import DerivedOrganization
from shared.utils.layered_config import ConfigFile, ConfigRole, GovernmentFormConfig

_PATH = "data_source/zz/local/config.yml"
_TOWN = "ocd-jurisdiction/country:us/state:zz/place:zytown/government"
_VILLAGE = "ocd-jurisdiction/country:us/state:zz/place:zyvillage/government"
_MANAGER_CITY = "ocd-jurisdiction/country:us/state:zz/place:zymanager/government"
_UNSAVED_CITY = "ocd-jurisdiction/country:us/state:zz/place:zyunsaved/government"
_ALL = [_TOWN, _VILLAGE, _MANAGER_CITY, _UNSAVED_CITY]
_HAND_LABELS = {"zz-test-member": "ZZ Test Selectperson"}


def _organization(name: str, *labels: str) -> DerivedOrganization:
    return DerivedOrganization(name=name, role_labels=list(labels))


def _config() -> ConfigFile:
    town = [
        _organization("Selectboard", "ZZ Test Select Board Member"),
        _organization("Town Officers", "ZZ Test Town Clerk"),
        _organization("Board of Listers", "ZZ Test Lister"),
    ]
    return ConfigFile(
        roles=[
            ConfigRole(id="zz-test-member", label="ZZ Test Member", aliases=["ZZ Test Select Board Member", "ZZ Test Council Member", "ZZ Test Trustee"]),
            ConfigRole(id="zz-test-mayor", label="ZZ Test Mayor"),
            ConfigRole(id="zz-test-clerk", label="ZZ Test Clerk", aliases=["ZZ Test Town Clerk", "ZZ Test Village Clerk"]),
            ConfigRole(id="zz-test-moderator", label="ZZ Test Moderator"),
            ConfigRole(id="zz-test-lister", label="ZZ Test Lister"),
            ConfigRole(id="zz-test-president", label="ZZ Test President", aliases=["ZZ Test Village President"]),
        ],
        government_forms={
            GovernmentForm.MAYOR_COUNCIL: GovernmentFormConfig(
                suffixes=["city"],
                organizations=[_organization("Council", "ZZ Test Council Member"), _organization("Office of the Mayor", "ZZ Test Mayor")],
            ),
            GovernmentForm.COUNCIL_MANAGER: GovernmentFormConfig(
                suffixes=["city"], organizations=[_organization("Council", "ZZ Test Council Member", "ZZ Test Mayor")]
            ),
            GovernmentForm.OPEN_TOWN_MEETING: GovernmentFormConfig(
                suffixes=["town"], organizations=[*town, _organization("Town Meeting", "ZZ Test Moderator")]
            ),
            GovernmentForm.REPRESENTATIVE_TOWN_MEETING: GovernmentFormConfig(
                suffixes=["town"], organizations=[*town, _organization("Town Meeting", "ZZ Test Moderator")]
            ),
            GovernmentForm.VILLAGE_BOARD: GovernmentFormConfig(
                suffixes=["village"],
                organizations=[
                    _organization("Board of Trustees", "ZZ Test Trustee", "ZZ Test Village President"),
                    _organization("Village Officers", "ZZ Test Village Clerk"),
                ],
            ),
        },
    )


async def _clean():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM organizations WHERE jurisdiction_ocdid = ANY(%s)", (_ALL,))
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = ANY(%s)", (_ALL,))
        await cur.execute("DELETE FROM roles WHERE id LIKE 'zz-test-%%'")
        await cur.execute("DELETE FROM jurisdiction_configs WHERE path = %s", (_PATH,))
        await cur.execute("DELETE FROM activity WHERE type = ANY(%s)", (["add_role", "edit_role", "delete_role", "sync_jurisdiction_config"],))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _clean()
    yield
    await _clean()


async def _seed() -> dict[str, str]:
    """The config stored; a town whose Selectboard a person already labelled, a village with its
    board from before, a city with a saved council_manager form, a city with none, each with a
    born default. Returns each default's id."""
    await jurisdiction_configs_db.sync_jurisdiction_config(
        JurisdictionConfigVersion(path=_PATH, commit_sha="abc123", pull_request_number=7), _config()
    )
    pool = await get_pool()
    ids = {}
    async with pool.connection() as conn, conn.cursor() as cur:
        for ocdid, name, form, default in (
            (_TOWN, "Zytown town", None, "Town Officers"),
            (_VILLAGE, "Zyvillage village", None, "Village Officers"),
            (_MANAGER_CITY, "Zymanager city", "council_manager", "City Officers"),
            (_UNSAVED_CITY, "Zyunsaved city", None, "City Officers"),
        ):
            await cur.execute(
                "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level, data, extras_government_form)"
                " VALUES (%s, 'zz', 'local', %s::jsonb, %s)",
                (ocdid, json.dumps({"name": name}), form),
            )
            await cur.execute(
                "INSERT INTO organizations (jurisdiction_ocdid, name, meta_is_default) VALUES (%s, %s, true) RETURNING id::text",
                (ocdid, default),
            )
            row = await cur.fetchone()
            assert row is not None
            ids[ocdid] = row[0]
        await cur.execute(
            "INSERT INTO organizations (jurisdiction_ocdid, name, extras_role_labels) VALUES (%s, 'Selectboard', %s::jsonb)",
            (_TOWN, json.dumps(_HAND_LABELS)),
        )
        await cur.execute("INSERT INTO organizations (jurisdiction_ocdid, name) VALUES (%s, 'Board of Trustees')", (_VILLAGE,))
        await conn.commit()
    return ids


async def _organizations(jurisdiction_ocdid: str) -> list[tuple[str, str, bool, dict]]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id::text, name, meta_is_default, extras_role_labels FROM organizations"
            " WHERE jurisdiction_ocdid = %s ORDER BY name",
            (jurisdiction_ocdid,),
        )
        return list(await cur.fetchall())


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_town_with_no_saved_form_gets_what_its_forms_share_and_its_default_keeps_its_id_and_gains_labels():
    ids = await _seed()

    created = await government_form_service.apply_config_organizations(_PATH)

    organizations = await _organizations(_TOWN)
    assert [name for _, name, _, _ in organizations] == ["Board of Listers", "Selectboard", "Town Meeting", "Town Officers"]
    by_name = {name: (id_, is_default, labels) for id_, name, is_default, labels in organizations}
    assert by_name["Town Officers"] == (ids[_TOWN], True, {"zz-test-clerk": "ZZ Test Town Clerk"})
    assert by_name["Selectboard"][2] == _HAND_LABELS
    assert by_name["Board of Listers"][2] == {}
    assert created == 2 + 0 + 1 + 1  # town: listers, meeting; village: none; each city: Council


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_village_keeps_its_board_and_both_get_their_labels():
    await _seed()

    await government_form_service.apply_config_organizations(_PATH)

    assert [(name, labels) for _, name, _, labels in await _organizations(_VILLAGE)] == [
        ("Board of Trustees", {"zz-test-member": "ZZ Test Trustee", "zz-test-president": "ZZ Test Village President"}),
        ("Village Officers", {"zz-test-clerk": "ZZ Test Village Clerk"}),
    ]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_city_gets_its_saved_forms_council_and_one_with_no_form_only_what_both_forms_share():
    await _seed()

    await government_form_service.apply_config_organizations(_PATH)

    assert [(name, labels) for _, name, _, labels in await _organizations(_MANAGER_CITY)] == [
        ("City Officers", {}),
        ("Council", {"zz-test-member": "ZZ Test Council Member"}),
    ]
    assert [name for _, name, _, _ in await _organizations(_UNSAVED_CITY)] == ["City Officers", "Council"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_applying_it_again_changes_nothing():
    await _seed()
    await government_form_service.apply_config_organizations(_PATH)
    before = [await _organizations(ocdid) for ocdid in _ALL]

    created = await government_form_service.apply_config_organizations(_PATH)

    assert created == 0
    assert [await _organizations(ocdid) for ocdid in _ALL] == before


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_country_roles_file_governs_no_organizations():
    await _seed()

    assert await government_form_service.apply_config_organizations("data_source/config.yml") == 0
    assert [name for _, name, _, _ in await _organizations(_TOWN)] == ["Selectboard", "Town Officers"]
