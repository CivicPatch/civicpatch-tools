"""Route-level integration tests for the role-config endpoints.

These run TestClient against the real test DB with auth mocked so the full
HTTP → Pydantic → service → DB stack is exercised. Catches bugs that direct
DB-layer tests miss (e.g. service-layer crashes, validation surprises,
wire-contract drift after schema changes).

Run with: mise run tcp-integration
"""
import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from database.database import get_pool
from lib.auth import get_optional_user
from routers.api import jurisdictions as jurisdictions_router
from schemas.common import Identity

# Sentinel scope — confined writes that won't collide with seeded data.
_SCOPE = "ocd-jurisdiction/country:us/state:zz/place:routetest/government"


def _fake_admin() -> Identity:
    # user_id=None matches the system-action pattern used elsewhere in
    # integration tests — change_logs.user_id allows NULL, so we sidestep
    # the need to seed a test user row just for FK satisfaction.
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
    app.include_router(jurisdictions_router.get_router(), prefix="/api/v1/jurisdictions")
    app.dependency_overrides[get_optional_user] = lambda: _fake_admin()
    return TestClient(app)


async def _wipe_scope():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM role_terms WHERE jurisdiction_ocdid = %s", (_SCOPE,))
        await cur.execute("DELETE FROM change_logs WHERE jurisdiction_ocdid = %s", (_SCOPE,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_scope():
    await _wipe_scope()
    yield
    await _wipe_scope()


async def _fetch_terms_for_scope() -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT value, is_unique FROM role_terms WHERE jurisdiction_ocdid = %s ORDER BY value",
            (_SCOPE,),
        )
        return [{"value": r[0], "is_unique": r[1]} for r in await cur.fetchall()]


async def _fetch_change_log_types() -> list[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT type FROM change_logs WHERE jurisdiction_ocdid = %s ORDER BY created_at",
            (_SCOPE,),
        )
        return [r[0] for r in await cur.fetchall()]


# ── PUT /config — batch save ────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.integration
async def test_put_config_add_canonical_role(client):
    """The bug from 2026-05-29: service-layer crash when service receives
    Pydantic models from a real PUT. This test would have caught it."""
    response = client.put("/api/v1/jurisdictions/config", json={
        "ocdid": _SCOPE,
        "scope": "locality",
        "roles": [{"role": "Mayor", "is_unique": True, "aliases": ["mayor"]}],
    })
    assert response.status_code == 200, response.text

    terms = await _fetch_terms_for_scope()
    assert terms == [{"value": "Mayor", "is_unique": True}]
    assert "add_role" in await _fetch_change_log_types()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_put_config_edit_is_unique_emits_edit_role(client):
    """Toggling is_unique without renaming was Bug 1 — silently dropped before
    the EDIT op was added. This test pins the fix."""
    client.put("/api/v1/jurisdictions/config", json={
        "ocdid": _SCOPE,
        "scope": "locality",
        "roles": [{"role": "Mayor", "is_unique": False, "aliases": []}],
    })

    response = client.put("/api/v1/jurisdictions/config", json={
        "ocdid": _SCOPE,
        "scope": "locality",
        "roles": [{"role": "Mayor", "is_unique": True, "aliases": []}],
    })
    assert response.status_code == 200, response.text

    terms = await _fetch_terms_for_scope()
    assert terms[0]["is_unique"] is True
    assert "edit_role" in await _fetch_change_log_types()


# ── POST /config/delete — surgical endpoint ─────────────────────────────


@pytest.mark.asyncio
@pytest.mark.integration
async def test_post_delete_removes_term(client):
    client.put("/api/v1/jurisdictions/config", json={
        "ocdid": _SCOPE,
        "scope": "locality",
        "roles": [{"role": "Mayor", "is_unique": False, "aliases": []}],
    })

    response = client.post("/api/v1/jurisdictions/config/delete", json={
        "role": "Mayor",
        "scope": "locality",
        "ocdid": _SCOPE,
    })
    assert response.status_code == 200, response.text

    assert await _fetch_terms_for_scope() == []
    assert "delete_role" in await _fetch_change_log_types()


# ── GET /config — wire-contract round trip ──────────────────────────────


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_config_round_trips_saved_roles(client):
    """Catches drift between what the DB layer emits and what the wire schema
    expects — a field the schema requires but the query omits would 500."""
    client.put("/api/v1/jurisdictions/config", json={
        "ocdid": _SCOPE,
        "scope": "locality",
        "roles": [
            {"role": "Mayor", "is_unique": True, "aliases": ["mayor"]},
            {"role": "Clerk", "is_unique": False, "aliases": []},
        ],
    })

    response = client.get("/api/v1/jurisdictions/config", params={"ocdid": _SCOPE})
    assert response.status_code == 200, response.text

    roles = response.json()["data"]["roles"]
    by_value = {r["role"]: r for r in roles}
    assert by_value["Mayor"]["is_unique"] is True
    assert by_value["Mayor"]["aliases"] == ["mayor"]
    assert by_value["Clerk"]["is_unique"] is False
