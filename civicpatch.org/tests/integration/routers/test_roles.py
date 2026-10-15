"""Route-level integration tests for the role endpoints.

These run TestClient against the real test DB with auth mocked so the full
HTTP → Pydantic → service → DB stack is exercised. Writes become open-data pull
requests (GitHub, unreachable here), so only the read is covered at this layer.

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

_PREFIX = "/api/v1/roles"
_SENTINEL_ID_PATTERN = "zz-route-%"


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
        await cur.execute("DELETE FROM roles WHERE id LIKE %s", (_SENTINEL_ID_PATTERN,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_roles():
    await _wipe()
    yield
    await _wipe()


async def _seed():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO roles (id, label, status, is_unique) VALUES"
            " ('zz-route-mayor', 'ZZ Route Mayor', 'active', true),"
            " ('zz-route-clerk', 'ZZ Route Clerk', 'active', false)"
        )
        await cur.execute(
            "INSERT INTO role_aliases (role_id, label, status) VALUES ('zz-route-mayor', 'zz mayor', 'active')"
        )
        await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_roles_round_trips_stored_roles(client):
    """Catches drift between what the DB layer emits and what the wire schema
    expects — a field the schema requires but the query omits would 500."""
    await _seed()

    response = client.get(_PREFIX)
    assert response.status_code == 200, response.text

    by_id = {r["id"]: r for r in response.json()["data"]["roles"]}
    assert by_id["zz-route-mayor"]["label"] == "ZZ Route Mayor"
    assert by_id["zz-route-mayor"]["is_unique"] is True
    assert by_id["zz-route-mayor"]["aliases"] == ["zz mayor"]
    assert by_id["zz-route-clerk"]["is_unique"] is False
