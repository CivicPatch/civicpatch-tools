"""Thin HTTP-contract tests for the role-config endpoints on the jurisdictions
router. Auth gating is exercised by overriding get_optional_user per role; the
service layer is mocked at the call boundary.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from lib.auth import get_optional_user
from routers.api import jurisdictions as jurisdictions_router
from schemas.common import Identity, Role
from shared.utils.config_utils import RoleConfig, RoleEntry


def _identity(role: Role) -> Identity:
    return Identity(
        type="cookie",
        provider="supabase",
        provider_user_id="user-uuid",
        email="user@example.com",
        role=role.value,
    )


def _client(role: Role) -> TestClient:
    app = FastAPI()
    app.dependency_overrides[get_optional_user] = lambda: _identity(role)
    app.include_router(jurisdictions_router.get_router(), prefix="/jurisdictions")
    return TestClient(app)


_OCDID = "ocd-jurisdiction/country:us/state:tx/place:austin"


# ── GET /config/global (MAINTAINERS) ────────────────────────────────────────


@pytest.mark.unit
def test_get_global_config_happy():
    config = RoleConfig(roles=[RoleEntry(role="Mayor", is_unique=False, aliases=["mayor"])])
    with patch("core.role_config.load_global_config", new_callable=AsyncMock, return_value=config):
        response = _client(Role.MAINTAINERS).get("/jurisdictions/config/global")

    assert response.status_code == 200
    roles = response.json()["data"]["roles"]
    assert roles == [{"role": "Mayor", "is_unique": False, "aliases": ["mayor"], "kind": "canonical"}]


@pytest.mark.unit
def test_get_global_config_forbidden_below_maintainer():
    response = _client(Role.CONTRIBUTORS).get("/jurisdictions/config/global")
    assert response.status_code == 403


# ── PUT /config/global (ADMINS) ─────────────────────────────────────────────


@pytest.mark.unit
def test_put_global_config_happy():
    body = {"roles": [{"role": "Mayor", "aliases": ["mayor"]}]}
    with patch("core.role_config.set_global_roles", new_callable=AsyncMock) as mock_set:
        response = _client(Role.ADMINS).put("/jurisdictions/config/global", json=body)

    assert response.status_code == 200
    assert response.json()["data"] == {"ok": True}
    mock_set.assert_awaited_once()


@pytest.mark.unit
def test_put_global_config_forbidden_for_maintainer():
    body = {"roles": []}
    response = _client(Role.MAINTAINERS).put("/jurisdictions/config/global", json=body)
    assert response.status_code == 403


# ── GET /config?ocdid= (MAINTAINERS) ────────────────────────────────────────


@pytest.mark.unit
def test_get_jurisdiction_config_happy():
    per_level = {"global": RoleConfig(roles=[RoleEntry(role="Mayor", aliases=[])])}
    with patch(
        "core.role_config.load_role_config_per_level",
        new_callable=AsyncMock,
        return_value=per_level,
    ):
        response = _client(Role.MAINTAINERS).get("/jurisdictions/config", params={"ocdid": _OCDID})

    assert response.status_code == 200
    roles = response.json()["data"]["roles"]
    assert any(r["role"] == "Mayor" and r["source"] == "global" for r in roles)


@pytest.mark.unit
def test_get_jurisdiction_config_invalid_ocdid_is_400():
    with patch(
        "core.role_config.load_role_config_per_level",
        new_callable=AsyncMock,
        side_effect=ValueError("bad ocdid"),
    ):
        response = _client(Role.MAINTAINERS).get("/jurisdictions/config", params={"ocdid": "garbage"})

    assert response.status_code == 400


# ── PUT /config (MAINTAINERS) ───────────────────────────────────────────────


@pytest.mark.unit
def test_put_jurisdiction_config_happy_calls_set_scope_roles():
    body = {"ocdid": _OCDID, "scope": "locality", "roles": [{"role": "Mayor"}]}
    with patch("core.role_config.set_scope_roles", new_callable=AsyncMock) as mock_set:
        response = _client(Role.MAINTAINERS).put("/jurisdictions/config", json=body)

    assert response.status_code == 200
    assert response.json()["data"] == {"ok": True}
    mock_set.assert_awaited_once()


@pytest.mark.unit
def test_put_jurisdiction_config_with_issue_id_routes_to_resolution():
    body = {"ocdid": _OCDID, "scope": "locality", "roles": [{"role": "Mayor"}], "issue_id": "issue-1"}
    with patch(
        "core.pipeline_issue_resolution.resolve_via_config_db", new_callable=AsyncMock
    ) as mock_resolve, patch(
        "core.role_config.set_scope_roles", new_callable=AsyncMock
    ) as mock_set:
        response = _client(Role.MAINTAINERS).put("/jurisdictions/config", json=body)

    assert response.status_code == 200
    mock_resolve.assert_awaited_once()
    mock_set.assert_not_awaited()


@pytest.mark.unit
def test_put_jurisdiction_config_runtime_error_is_409():
    body = {"ocdid": _OCDID, "scope": "locality", "roles": []}
    with patch(
        "core.role_config.set_scope_roles",
        new_callable=AsyncMock,
        side_effect=RuntimeError("conflict"),
    ):
        response = _client(Role.MAINTAINERS).put("/jurisdictions/config", json=body)

    assert response.status_code == 409
