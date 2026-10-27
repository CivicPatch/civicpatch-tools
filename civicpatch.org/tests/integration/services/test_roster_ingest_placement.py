"""`reconcile_scrape` against real organization rows and config: a pipeline row goes to the
organization the model picked, else the one whose form lists its post role, else the one of
those the person already sits in, else the default.

Isolation: place `zyplace_town` in ma and the two config paths below, cleaned after.
"""

import datetime
import json

import pytest
import pytest_asyncio

from database.database import get_pool
from database.organizations import ensure_defaults_exist
from services.roster_ingest import reconcile_scrape
from tests.integration import factories
from shared.schemas import GovernmentForm, Role, RoleConfig, SelectionMethod
from shared.utils.government_forms import DerivedOrganization
from shared.utils.layered_config import COUNTRY_ROLES_PATH, ConfigFile, ConfigRole, GovernmentFormConfig
from shared.utils.taxonomy import build_taxonomy

_TOWN = "ocd-jurisdiction/country:us/state:ma/place:zyplace_town/government"
_ROLES = [
    ConfigRole(id="member", label="Member", aliases=["Select Board Member"]),
    ConfigRole(id="chair", label="Chair", is_unique=True, selection_method=SelectionMethod.ELECTED_BY_MEMBERS),
    ConfigRole(id="clerk", label="Clerk", is_unique=True, aliases=["Town Clerk"]),
    ConfigRole(id="moderator", label="Moderator", is_unique=True),
]
_CONFIGS = {
    COUNTRY_ROLES_PATH: ConfigFile(roles=_ROLES),
    "data_source/local/config.yml": ConfigFile(
        government_forms={
            GovernmentForm.OPEN_TOWN_MEETING: GovernmentFormConfig(
                organizations=[
                    DerivedOrganization(name="Select Board", role_labels=["Select Board Member", "Chair"]),
                    DerivedOrganization(name="Town Meeting", role_labels=["Moderator"]),
                    DerivedOrganization(name="Town Officers", role_labels=["Town Clerk"]),
                ]
            )
        }
    ),
}
TAXONOMY = build_taxonomy(RoleConfig(roles=[Role(**role.model_dump()) for role in _ROLES]))


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
            """
            INSERT INTO jurisdictions (jurisdiction_ocdid, state, data, updated_at, extras_government_form)
            VALUES (%s, 'ma', %s::jsonb, now(), 'open_town_meeting')
            """,
            (_TOWN, json.dumps({"name": "Zyplace town"})),
        )
        await conn.commit()
    await ensure_defaults_exist([_TOWN])
    async with pool.connection() as conn, conn.cursor() as cur:
        for name in ("Select Board", "Town Meeting"):
            await cur.execute("INSERT INTO organizations (jurisdiction_ocdid, name) VALUES (%s, %s)", (_TOWN, name))
        await conn.commit()
    yield
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM activity WHERE jurisdiction_ocdid = %s", (_TOWN,))
        await cur.execute("DELETE FROM source_records WHERE jurisdiction_ocdid = %s", (_TOWN,))
        await cur.execute("DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_TOWN,))
        await cur.execute("DELETE FROM organizations WHERE jurisdiction_ocdid = %s", (_TOWN,))
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_TOWN,))
        await cur.execute("DELETE FROM jurisdiction_configs WHERE path = ANY(%s)", (list(_CONFIGS),))
        await conn.commit()


async def _ids_by_name() -> dict[str, str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT name, id::text FROM organizations WHERE jurisdiction_ocdid = %s", (_TOWN,))
        return dict(await cur.fetchall())


def _row(name: str, label: str, organization_id: str | None) -> dict:
    return {"name": name, "label": label, "organization_id": organization_id, "source_url": "https://zyplace.gov"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_each_row_goes_to_its_pick_then_its_role_then_where_it_sits_then_the_default():
    ids = await _ids_by_name()
    await factories.published_source_record(
        _TOWN, ids["Select Board"], "11111111-1111-4111-8111-111111111111", "Dee Moss", "Select Board Member",
        "https://zyplace.gov/select-board", datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
    )
    rows = [
        _row("Ann Lee", "Town Clerk", ids["Town Meeting"]),
        _row("Bo Ray", "Town Clerk", None),
        _row("Cy Fox", "Select Board Member", None),
        _row("Dee Moss", "Chair", None),
    ]

    roster, records_by_person = await reconcile_scrape(_TOWN, rows, {}, TAXONOMY)

    placed = {person["name"]: records_by_person[person["id"]][0]["organization_id"] for person in roster}
    assert placed == {
        "Ann Lee": ids["Town Meeting"],
        "Bo Ray": ids["Town Officers"],
        "Cy Fox": ids["Town Officers"],
        "Dee Moss": ids["Select Board"],
    }
