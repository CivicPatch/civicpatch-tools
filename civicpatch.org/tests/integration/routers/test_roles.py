"""Route-level integration tests for the role endpoint.

These run TestClient against the real test DB with auth mocked so the full
HTTP → Pydantic → service → DB stack is exercised. Roles are read from the stored
config files: a level's, with a state's additions when one is named.

Run with: mise run tcp-integration
"""
import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from database.database import get_pool
from lib.auth import get_optional_user
from routers.api import roles as roles_router
from schemas.common import Identity
from shared.utils.layered_config import ConfigFile, ConfigRole

_PREFIX = "/api/v1/roles"
_ZZ_LOCAL = "data_source/zz/local/config.yml"
_ZZ_LOCAL_CONFIG = ConfigFile(
    roles=[
        ConfigRole(id="zz-route-mayor", label="ZZ Route Mayor", is_unique=True, aliases=["zz mayor"]),
        ConfigRole(id="zz-route-clerk", label="ZZ Route Clerk"),
    ],
    role_aliases={"member": ["zz route alderperson"]},
)


def _fake_admin() -> Identity:
    return Identity(
        type="session",
        provider="email",
        provider_user_id="route-test-admin",
        email="route-test@example.com",
        role="admins",
        user_id=None,
    )


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(roles_router.get_router(), prefix=_PREFIX)
    app.dependency_overrides[get_optional_user] = lambda: _fake_admin()
    return TestClient(app)


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM jurisdiction_configs WHERE path = %s", (_ZZ_LOCAL,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def zz_state_config():
    await _wipe()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdiction_configs (path, content, commit_sha) VALUES (%s, %s, 'test')",
            (_ZZ_LOCAL, _ZZ_LOCAL_CONFIG.model_dump_json()),
        )
        await conn.commit()
    yield
    await _wipe()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_roles_round_trips_a_states_roles(client):
    """Catches drift between what the config layer emits and what the wire schema
    expects — a field the schema requires but the merge omits would 500."""
    response = client.get(_PREFIX, params={"level": "local", "state": "zz"})
    assert response.status_code == 200, response.text

    by_id = {r["id"]: r for r in response.json()["data"]["roles"]}
    assert by_id["zz-route-mayor"]["label"] == "ZZ Route Mayor"
    assert by_id["zz-route-mayor"]["is_unique"] is True
    assert by_id["zz-route-mayor"]["aliases"] == ["zz mayor"]
    assert by_id["zz-route-clerk"]["is_unique"] is False
    assert "zz route alderperson" in by_id["member"]["aliases"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_jurisdiction_gets_its_own_level_and_states_roles(client):
    place = "ocd-jurisdiction/country:us/state:zz/place:route_town/government"
    county = "ocd-jurisdiction/country:us/state:zz/county:route_county/government"

    place_roles = client.get(_PREFIX, params={"jurisdiction_ocdid": place}).json()["data"]["roles"]
    county_roles = client.get(_PREFIX, params={"jurisdiction_ocdid": county}).json()["data"]["roles"]

    assert "zz-route-mayor" in [role["id"] for role in place_roles]
    assert "zz-route-mayor" not in [role["id"] for role in county_roles]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_ocdid_that_names_no_jurisdiction_is_refused(client):
    response = client.get(_PREFIX, params={"jurisdiction_ocdid": "not-an-ocdid"})

    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_level_alone_leaves_out_every_states_roles(client):
    response = client.get(_PREFIX, params={"level": "local"})
    assert response.status_code == 200, response.text

    by_id = {r["id"]: r for r in response.json()["data"]["roles"]}
    assert "member" in by_id
    assert "zz-route-mayor" not in by_id
    assert "zz route alderperson" not in by_id["member"]["aliases"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_no_level_is_every_role_with_every_files_aliases(client):
    response = client.get(_PREFIX)
    assert response.status_code == 200, response.text

    by_id = {r["id"]: r for r in response.json()["data"]["roles"]}
    assert "zz-route-mayor" in by_id
    assert "zz route alderperson" in by_id["member"]["aliases"]
