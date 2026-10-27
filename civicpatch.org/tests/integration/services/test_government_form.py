"""`resolved_government` against real jurisdiction rows: its government form wins, then
the config, and a state or an unknown jurisdiction resolves to nothing.

The config is a small set of `jurisdiction_configs` rows the fixture writes, shaped like
open-data's files for the states used here.
"""

import json

import pytest
import pytest_asyncio

from database.database import get_pool
from database.organizations import ensure_defaults_exist
from services.government_form import (
    government_form_summary,
    organizations_with_role_labels,
    resolved_government,
)
from shared.schemas import GovernmentForm
from shared.utils.government_forms import DerivedOrganization
from shared.utils.layered_config import COUNTRY_ROLES_PATH, ConfigFile, ConfigRole, GovernmentFormConfig

_MI_TOWNSHIP = "ocd-jurisdiction/country:us/state:mi/place:zyform_township/government"
_WA_CITY = "ocd-jurisdiction/country:us/state:wa/place:zyform_city/government"
_WA_STATE = "ocd-jurisdiction/country:us/state:wa/government"
_UNKNOWN = "ocd-jurisdiction/country:us/state:wa/place:zyform_missing/government"
_MA_TOWN = "ocd-jurisdiction/country:us/state:ma/place:zyform_town/government"
_TX_COUNTY = "ocd-jurisdiction/country:us/state:tx/county:zyform/government"
_TN_COUNTY = "ocd-jurisdiction/country:us/state:tn/county:zyform/government"
_WA_COUNTY = "ocd-jurisdiction/country:us/state:wa/county:zyform/government"


async def _seed(
    jurisdiction_ocdid: str, state: str, data: dict, government_form: str | None = None
) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO jurisdictions
                (jurisdiction_ocdid, state, data, updated_at, extras_government_form)
            VALUES (%s, %s, %s::jsonb, now(), %s)
            ON CONFLICT (jurisdiction_ocdid) DO UPDATE
                SET data = EXCLUDED.data, extras_government_form = EXCLUDED.extras_government_form
            """,
            (jurisdiction_ocdid, state, json.dumps(data), government_form),
        )
        await conn.commit()


def _organization(name: str, *role_labels: str) -> DerivedOrganization:
    return DerivedOrganization(name=name, role_labels=list(role_labels))


def _forms(**organizations_by_form: list[DerivedOrganization]) -> ConfigFile:
    return ConfigFile(
        government_forms={
            GovernmentForm(form): GovernmentFormConfig(organizations=organizations)
            for form, organizations in organizations_by_form.items()
        }
    )


_ROLE_LABELS = [
    "Mayor", "Council Member", "Commissioner", "Supervisor", "Treasurer", "Trustee",
    "Select Board Member", "Chair", "Vice Chair", "Moderator", "County Executive",
]
_CONFIGS = {
    COUNTRY_ROLES_PATH: ConfigFile(
        roles=[
            *[ConfigRole(id=label.lower().replace(" ", "-"), label=label) for label in _ROLE_LABELS],
            ConfigRole(id="clerk", label="Clerk", aliases=["Town Clerk"]),
        ]
    ),
    "data_source/local/config.yml": _forms(
        mayor_council=[_organization("Council", "Council Member"), _organization("Office of the Mayor", "Mayor")],
        council_manager=[_organization("Council", "Council Member", "Mayor")],
        township_board=[_organization("Board", "Supervisor", "Clerk", "Treasurer", "Trustee")],
        open_town_meeting=[
            _organization("Select Board", "Select Board Member", "Chair", "Vice Chair"),
            _organization("Town Meeting", "Moderator"),
            _organization("Town Officers", "Town Clerk", "Treasurer"),
        ],
    ),
    "data_source/counties/config.yml": _forms(
        commission=[_organization("Board of Commissioners", "Commissioner", "Chair")],
        county_executive=[
            _organization("County Council", "Council Member", "Chair"),
            _organization("County Executive", "County Executive"),
        ],
    ),
    "data_source/mi/local/config.yml": ConfigFile(
        government_forms={GovernmentForm.TOWNSHIP_BOARD: GovernmentFormConfig(suffixes=["township"])}
    ),
    "data_source/tx/counties/config.yml": _forms(
        commission=[_organization("Commissioners Court", "Commissioner")]
    ),
    "data_source/tn/counties/config.yml": _forms(
        county_executive=[
            _organization("County Commission", "Commissioner", "Chair"),
            _organization("Office of the County Mayor", "Mayor"),
        ]
    ),
    "data_source/wa/counties/config.yml": _forms(
        commission=[_organization("Board of County Commissioners", "Commissioner", "Chair")]
    ),
}


@pytest_asyncio.fixture(autouse=True)
async def _configs():
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
        await conn.commit()
    yield
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM jurisdiction_configs WHERE path = ANY(%s)", (list(_CONFIGS),))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def _cleanup():
    yield
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        seeded = [_MI_TOWNSHIP, _WA_CITY, _MA_TOWN, _TX_COUNTY, _TN_COUNTY, _WA_COUNTY]
        await cur.execute("DELETE FROM activity WHERE jurisdiction_ocdid = ANY(%s)", (seeded,))
        await cur.execute("DELETE FROM organizations WHERE jurisdiction_ocdid = ANY(%s)", (seeded,))
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = ANY(%s)", (seeded,))
        await conn.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_config_rule_decides_a_michigan_township():
    await _seed(_MI_TOWNSHIP, "mi", {"name": "Zyform township"})

    assert (await resolved_government(_MI_TOWNSHIP)).government_form == GovernmentForm.TOWNSHIP_BOARD


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_government_form_beats_the_config_rule():
    await _seed(_MI_TOWNSHIP, "mi", {"name": "Zyform township"}, government_form="mayor_council")

    assert (await resolved_government(_MI_TOWNSHIP)).government_form == GovernmentForm.MAYOR_COUNCIL


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_city_the_config_leaves_open_resolves_to_nothing():
    await _seed(_WA_CITY, "wa", {"name": "Zyform city"})

    assert (await resolved_government(_WA_CITY)).government_form is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_state_resolves_to_nothing():
    assert (await resolved_government(_WA_STATE)).government_form is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_an_unknown_jurisdiction_resolves_to_nothing():
    assert (await resolved_government(_UNKNOWN)).government_form is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_tennessee_county_resolves_to_its_board_and_mayors_office():
    await _seed(_TN_COUNTY, "tn", {"name": "Zyform County"})

    resolved = await resolved_government(_TN_COUNTY)

    assert resolved.government_form == GovernmentForm.COUNTY_EXECUTIVE
    assert [o.name for o in resolved.candidate_organizations] == [
        "County Commission",
        "Office of the County Mayor",
    ]


async def _resolved_form(jurisdiction_ocdid: str) -> str | None:
    form = (await resolved_government(jurisdiction_ocdid)).government_form
    return form.value if form is not None else None


async def _insert_organizations(jurisdiction_ocdid: str, names: list[str]) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        for name in names:
            await cur.execute(
                "INSERT INTO organizations (jurisdiction_ocdid, name) VALUES (%s, %s)", (jurisdiction_ocdid, name)
            )
        await conn.commit()


async def _rename_default(jurisdiction_ocdid: str, name: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE organizations SET name = %s WHERE jurisdiction_ocdid = %s AND meta_is_default",
            (name, jurisdiction_ocdid),
        )
        await conn.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_organizations_carry_their_derived_role_labels():
    """The organizations a state's migration creates, beside the born default."""
    await _seed(_TN_COUNTY, "tn", {"name": "Zyform County"})
    await ensure_defaults_exist([_TN_COUNTY])
    await _insert_organizations(_TN_COUNTY, ["County Commission", "Office of the County Mayor"])

    organizations = await organizations_with_role_labels(_TN_COUNTY)

    assert {o["name"]: o["role_labels"] for o in organizations} == {
        "County Officers": [],
        "County Commission": ["Commissioner", "Chair"],
        "Office of the County Mayor": ["Mayor"],
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_while_the_form_is_unknown_an_organization_carries_every_allowed_forms_labels():
    """Zyform city could be mayor_council or council_manager; its Council gets both forms' roles."""
    await _seed(_WA_CITY, "wa", {"name": "Zyform city"})
    await ensure_defaults_exist([_WA_CITY])
    await _rename_default(_WA_CITY, "Council")

    organizations = await organizations_with_role_labels(_WA_CITY)

    assert {o["name"]: o["role_labels"] for o in organizations} == {"Council": ["Council Member", "Mayor"]}
    assert (await resolved_government(_WA_CITY)).government_form is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_page_shows_the_resolved_form_by_name():
    await _seed(_TN_COUNTY, "tn", {"name": "Zyform County"})

    summary = await government_form_summary(_TN_COUNTY)

    assert summary is not None
    assert (summary.value, summary.name) == (GovernmentForm.COUNTY_EXECUTIVE, "County executive")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_page_shows_no_form_when_none_is_known():
    await _seed(_WA_CITY, "wa", {"name": "Zyform city"})

    assert await government_form_summary(_WA_CITY) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_allowed_forms_are_what_an_undecided_jurisdiction_is_offered():
    await _seed(_WA_CITY, "wa", {"name": "Zyform city"})
    await _seed(_MI_TOWNSHIP, "mi", {"name": "Zyform township"})

    assert len((await resolved_government(_WA_CITY)).candidate_government_forms) == 4
    assert (await resolved_government(_MI_TOWNSHIP)).candidate_government_forms == [GovernmentForm.TOWNSHIP_BOARD]
