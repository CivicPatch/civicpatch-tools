"""Route-level integration tests for the role endpoints.

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
from routers.api import roles as roles_router
from schemas.common import Identity

_PREFIX = "/api/v1/roles"
_SENTINEL_PREFIX = "ZZ Route "
_SENTINEL_ID_PATTERN = "zz-route-%"
_ROLE_LOG_TYPES = ["add_role", "edit_role", "delete_role", "reorder_roles"]


def _label(name: str) -> str:
    return f"{_SENTINEL_PREFIX}{name}"


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
    app.include_router(roles_router.get_router(), prefix=_PREFIX)
    app.dependency_overrides[get_optional_user] = lambda: _fake_admin()
    return TestClient(app)


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM roles WHERE id LIKE %s", (_SENTINEL_ID_PATTERN,))
        await cur.execute("DELETE FROM change_logs WHERE type = ANY(%s)", (_ROLE_LOG_TYPES,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_roles():
    await _wipe()
    yield
    await _wipe()


async def _fetch_sentinel_rows() -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id, label, status, is_unique FROM roles WHERE id LIKE %s ORDER BY label",
            (_SENTINEL_ID_PATTERN,),
        )
        return [
            {"id": r[0], "label": r[1], "status": r[2], "is_unique": r[3]}
            for r in await cur.fetchall()
        ]


async def _fetch_change_log_types() -> list[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT type FROM change_logs WHERE type = ANY(%s) ORDER BY created_at",
            (_ROLE_LOG_TYPES,),
        )
        return [r[0] for r in await cur.fetchall()]


# ── PUT /roles — batch save ─────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.integration
async def test_put_roles_adds_role(client):
    """The bug from 2026-05-29: service-layer crash when the service receives
    Pydantic models from a real PUT. This test would have caught it."""
    response = client.put(_PREFIX, json={
        "roles": [{"label": _label("Mayor"), "is_unique": True, "aliases": ["zz mayor"]}],
    })
    assert response.status_code == 200, response.text

    rows = await _fetch_sentinel_rows()
    assert rows == [{
        "id": "zz-route-mayor",
        "label": _label("Mayor"),
        "status": "active",
        "is_unique": True,
    }]
    assert "add_role" in await _fetch_change_log_types()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_put_roles_edit_is_unique_emits_edit_role(client):
    """Toggling is_unique without renaming was Bug 1 — silently dropped before
    the EDIT op was added. This test pins the fix."""
    client.put(_PREFIX, json={
        "roles": [{"label": _label("Mayor"), "is_unique": False, "aliases": []}],
    })

    response = client.put(_PREFIX, json={
        "roles": [{"label": _label("Mayor"), "is_unique": True, "aliases": []}],
    })
    assert response.status_code == 200, response.text

    rows = await _fetch_sentinel_rows()
    assert rows[0]["is_unique"] is True
    assert "edit_role" in await _fetch_change_log_types()


# ── DELETE /roles/{role_id} ─────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_role_deactivates_rather_than_removing(client):
    client.put(_PREFIX, json={
        "roles": [{"label": _label("Mayor"), "is_unique": False, "aliases": []}],
    })

    response = client.delete(f"{_PREFIX}/zz-route-mayor")
    assert response.status_code == 200, response.text

    rows = await _fetch_sentinel_rows()
    assert rows[0]["status"] == "inactive", "the row must survive so seat history can"
    assert "delete_role" in await _fetch_change_log_types()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_unknown_role_is_404(client):
    assert client.delete(f"{_PREFIX}/zz-route-nonexistent").status_code == 404


# ── GET /roles — wire-contract round trip ───────────────────────────────


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_roles_round_trips_saved_roles(client):
    """Catches drift between what the DB layer emits and what the wire schema
    expects — a field the schema requires but the query omits would 500."""
    client.put(_PREFIX, json={
        "roles": [
            {"label": _label("Mayor"), "is_unique": True, "aliases": ["zz mayor"]},
            {"label": _label("Clerk"), "is_unique": False, "aliases": []},
        ],
    })

    response = client.get(_PREFIX)
    assert response.status_code == 200, response.text

    by_label = {r["label"]: r for r in response.json()["data"]["roles"]}
    assert by_label[_label("Mayor")]["is_unique"] is True
    assert by_label[_label("Mayor")]["aliases"] == ["zz mayor"]
    assert by_label[_label("Clerk")]["is_unique"] is False
    # The derived id is part of the wire contract now, not an internal detail.
    assert by_label[_label("Mayor")]["id"] == "zz-route-mayor"
