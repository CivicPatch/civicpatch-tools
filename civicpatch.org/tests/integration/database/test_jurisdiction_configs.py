"""Integration tests for applying a synced open-data config file (database.jurisdiction_configs).

Against the real test DB, so the alias index, the stored jsonb and the activity rows are
exercised. Every write uses a state path no real file has and sentinel role ids, and the fixture
removes both, so the seeded country roles are never touched.
"""

from typing import LiteralString

import pytest
import pytest_asyncio

from database.database import get_pool
from database.jurisdiction_configs import sync_jurisdiction_config
from schemas.jurisdiction_configs import JurisdictionConfigVersion
from shared.schemas import GovernmentForm
from shared.utils.government_forms import DerivedOrganization
from shared.utils.layered_config import ConfigFile, ConfigRole, FormConfig

_PATH = "data_source/zz/local/config.yml"
_SENTINEL_ID_PATTERN = "zz-test-%"
_ACTIVITY_TYPES = ["add_role", "edit_role", "delete_role", "sync_jurisdiction_config"]


async def _clean():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM roles WHERE id LIKE %s", (_SENTINEL_ID_PATTERN,))
        await cur.execute("DELETE FROM jurisdiction_configs WHERE path = %s", (_PATH,))
        await cur.execute("DELETE FROM activity WHERE type = ANY(%s)", (_ACTIVITY_TYPES,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_configs():
    await _clean()
    yield
    await _clean()


def _version(commit_sha: str = "abc123") -> JurisdictionConfigVersion:
    return JurisdictionConfigVersion(path=_PATH, commit_sha=commit_sha, pull_request_number=7)


def _role(id_: str, label: str, aliases: list[str] | None = None) -> ConfigRole:
    return ConfigRole(id=f"zz-test-{id_}", label=f"ZZ Test {label}", aliases=aliases or [])


async def _fetch(sql: LiteralString, params=()):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchall()


async def _roles():
    return await _fetch(
        """
        SELECT r.id, r.label, r.status, r.priority, r.config_path,
               array_agg(a.label ORDER BY a.label) FILTER (WHERE a.id IS NOT NULL)
        FROM roles r LEFT JOIN role_aliases a ON a.role_id = r.id
        WHERE r.id LIKE %s GROUP BY r.id ORDER BY r.id
        """,
        (_SENTINEL_ID_PATTERN,),
    )


async def _activity():
    return await _fetch(
        "SELECT type, changes FROM activity WHERE type = ANY(%s)",
        (_ACTIVITY_TYPES,),
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_first_sync_adds_the_roles_and_stores_the_file():
    config = ConfigFile(roles=[_role("warden", "Warden", ["zz town warden"])])

    await sync_jurisdiction_config(_version(), config)

    assert await _roles() == [
        ("zz-test-warden", "ZZ Test Warden", "active", None, _PATH, ["zz town warden"])
    ]
    [(content, commit_sha)] = await _fetch(
        "SELECT content, commit_sha FROM jurisdiction_configs WHERE path = %s", (_PATH,)
    )
    assert (ConfigFile.model_validate(content), commit_sha) == (config, "abc123")
    changes_by_type = {type_: changes for type_, changes in await _activity()}
    assert sorted(changes_by_type) == ["add_role", "sync_jurisdiction_config"]
    assert changes_by_type["add_role"]["pull_request_number"] == 7
    assert changes_by_type["sync_jurisdiction_config"]["path"] == _PATH


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_later_sync_renames_moves_aliases_and_deactivates():
    await sync_jurisdiction_config(
        _version(),
        ConfigFile(roles=[_role("warden", "Warden", ["zz town warden"]), _role("reeve", "Reeve")]),
    )

    await sync_jurisdiction_config(
        _version("def456"),
        ConfigFile(roles=[_role("warden", "Head Warden", ["zz chief warden"])]),
    )

    assert await _roles() == [
        ("zz-test-reeve", "ZZ Test Reeve", "inactive", None, _PATH, None),
        ("zz-test-warden", "ZZ Test Head Warden", "active", None, _PATH, ["zz chief warden"]),
    ]
    later = [
        (type_, changes.get("role")) for type_, changes in await _activity() if changes["commit_sha"] == "def456"
    ]
    assert sorted(later, key=str) == sorted(
        [
            ("edit_role", "ZZ Test Head Warden"),
            ("delete_role", "ZZ Test Reeve"),
            ("sync_jurisdiction_config", None),
        ],
        key=str,
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_sync_row_names_the_forms_that_changed():
    mayor = DerivedOrganization(name="Office of the Mayor", role_labels=["Mayor"])
    await sync_jurisdiction_config(
        _version(), ConfigFile(government_forms={GovernmentForm.COMMISSION: FormConfig()})
    )

    await sync_jurisdiction_config(
        _version("def456"),
        ConfigFile(government_forms={GovernmentForm.MAYOR_COUNCIL: FormConfig(organizations=[mayor])}),
    )

    [last_sync] = [
        changes for type_, changes in await _activity()
        if type_ == "sync_jurisdiction_config" and changes["commit_sha"] == "def456"
    ]
    assert last_sync["forms"] == {"added": ["mayor_council"], "removed": ["commission"], "changed": []}
