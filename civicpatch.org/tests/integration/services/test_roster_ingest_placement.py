"""`placed_by_role` against real organization rows and config: a pipeline row goes to the
organization whose form lists its post role, else to the one it was stamped with, else the default.

Isolation: place `zyplace_town` in ma and the two config paths below, cleaned after.
"""

import json

import pytest
import pytest_asyncio

from database.database import get_pool
from database.organizations import ensure_defaults_exist
from services.roster_ingest import placed_by_role
from shared.schemas import GovernmentForm, Role, RoleConfig
from shared.utils.government_forms import DerivedOrganization
from shared.utils.layered_config import COUNTRY_ROLES_PATH, ConfigFile, ConfigRole, GovernmentFormConfig
from shared.utils.taxonomy import build_taxonomy

_TOWN = "ocd-jurisdiction/country:us/state:ma/place:zyplace_town/government"
_ROLES = [
    ConfigRole(id="member", label="Member", aliases=["Select Board Member"]),
    ConfigRole(id="clerk", label="Clerk", is_unique=True, aliases=["Town Clerk"]),
    ConfigRole(id="moderator", label="Moderator", is_unique=True),
]
_CONFIGS = {
    COUNTRY_ROLES_PATH: ConfigFile(roles=_ROLES),
    "data_source/local/config.yml": ConfigFile(
        government_forms={
            GovernmentForm.OPEN_TOWN_MEETING: GovernmentFormConfig(
                organizations=[
                    DerivedOrganization(name="Select Board", role_labels=["Select Board Member"]),
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
async def test_each_row_goes_to_its_role_then_its_stamp_then_the_default():
    ids = await _ids_by_name()
    rows = [
        _row("Ann", "Town Clerk", ids["Town Meeting"]),
        _row("Bo", "Select Board Member", ids["Select Board"]),
        _row("Cy", "Select Board Member", None),
    ]

    placed = await placed_by_role(_TOWN, rows, TAXONOMY)

    assert {row["name"]: row["organization_id"] for row in placed} == {
        "Ann": ids["Town Officers"],
        "Bo": ids["Select Board"],
        "Cy": ids["Town Officers"],
    }
