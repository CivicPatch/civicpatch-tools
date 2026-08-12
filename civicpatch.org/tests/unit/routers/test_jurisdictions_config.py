"""Thin HTTP-contract tests for the role-config endpoints on the jurisdictions
router. Auth gating is exercised by overriding get_optional_user per role; the
service layer is mocked at the call boundary.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from lib.auth import get_optional_user
from routers.api import jurisdictions as jurisdictions_router
from schemas.common import Identity, UserRole
from shared.schemas import Role, RoleConfig


def _identity(role: UserRole) -> Identity:
    return Identity(
        type="cookie",
        provider="supabase",
        provider_user_id="user-uuid",
        email="user@example.com",
        role=role.value,
    )


def _client(role: UserRole) -> TestClient:
    app = FastAPI()
    app.dependency_overrides[get_optional_user] = lambda: _identity(role)
    app.include_router(jurisdictions_router.get_router(), prefix="/jurisdictions")
    return TestClient(app)


_OCDID = "ocd-jurisdiction/country:us/state:tx/place:austin"


# ── GET /config/global (MAINTAINERS) ────────────────────────────────────────


@pytest.mark.unit
def test_get_global_config_happy():
    config = RoleConfig(roles=[Role(label="Mayor", is_unique=False, aliases=["mayor"])])
    with patch(
        "services.role_config.load_global_config",
        new_callable=AsyncMock,
        return_value=config,
    ):
        response = _client(UserRole.MAINTAINERS).get("/jurisdictions/config/global")

    assert response.status_code == 200
    roles = response.json()["data"]["roles"]
    assert roles == [
        {
            "role": "Mayor",
            "label": "Mayor",
            "status": None,
            "is_unique": False,
            "priority": None,
            "aliases": ["mayor"],
        }
    ]


@pytest.mark.unit
def test_get_global_config_forbidden_below_maintainer():
    response = _client(UserRole.CONTRIBUTORS).get("/jurisdictions/config/global")
    assert response.status_code == 403


# ── PUT /config/global (ADMINS) ─────────────────────────────────────────────


@pytest.mark.unit
def test_put_global_config_happy():
    body = {"roles": [{"label": "Mayor", "aliases": ["mayor"]}]}
    with patch(
        "services.role_config.set_global_roles", new_callable=AsyncMock
    ) as mock_set:
        response = _client(UserRole.ADMINS).put("/jurisdictions/config/global", json=body)

    assert response.status_code == 200
    assert response.json()["data"] == {"ok": True}
    mock_set.assert_awaited_once()


@pytest.mark.unit
def test_put_global_config_forbidden_for_maintainer():
    body = {"roles": []}
    response = _client(UserRole.MAINTAINERS).put("/jurisdictions/config/global", json=body)
    assert response.status_code == 403


# ── GET /config?ocdid= (MAINTAINERS) ────────────────────────────────────────


@pytest.mark.unit
def test_get_jurisdiction_config_happy():
    per_level = {"global": RoleConfig(roles=[Role(label="Mayor", aliases=[])])}
    with patch(
        "services.role_config.load_role_config_per_level",
        new_callable=AsyncMock,
        return_value=per_level,
    ):
        response = _client(UserRole.MAINTAINERS).get(
            "/jurisdictions/config", params={"ocdid": _OCDID}
        )

    assert response.status_code == 200
    roles = response.json()["data"]["roles"]
    assert any(r["label"] == "Mayor" and r["scope"] == "global" for r in roles)


@pytest.mark.unit
def test_get_jurisdiction_config_invalid_ocdid_is_400():
    with patch(
        "services.role_config.load_role_config_per_level",
        new_callable=AsyncMock,
        side_effect=ValueError("bad ocdid"),
    ):
        response = _client(UserRole.MAINTAINERS).get(
            "/jurisdictions/config", params={"ocdid": "garbage"}
        )

    assert response.status_code == 400


# ── PUT /config (MAINTAINERS) ───────────────────────────────────────────────


@pytest.mark.unit
def test_put_jurisdiction_config_happy_calls_set_scope_roles():
    body = {"ocdid": _OCDID, "scope": "locality", "roles": [{"label": "Mayor"}]}
    with patch(
        "services.role_config.set_scope_roles", new_callable=AsyncMock
    ) as mock_set:
        response = _client(UserRole.MAINTAINERS).put("/jurisdictions/config", json=body)

    assert response.status_code == 200
    assert response.json()["data"] == {"ok": True}
    mock_set.assert_awaited_once()


@pytest.mark.unit
def test_put_jurisdiction_config_with_issue_id_routes_to_resolution():
    body = {
        "ocdid": _OCDID,
        "scope": "locality",
        "roles": [{"label": "Mayor"}],
        "issue_id": "issue-1",
    }
    with (
        patch(
            "services.pipeline_issue_resolution.resolve_via_config_db",
            new_callable=AsyncMock,
        ) as mock_resolve,
        patch(
            "services.role_config.set_scope_roles", new_callable=AsyncMock
        ) as mock_set,
    ):
        response = _client(UserRole.MAINTAINERS).put("/jurisdictions/config", json=body)

    assert response.status_code == 200
    mock_resolve.assert_awaited_once()
    mock_set.assert_not_awaited()


@pytest.mark.unit
def test_put_jurisdiction_config_runtime_error_is_409():
    body = {"ocdid": _OCDID, "scope": "locality", "roles": []}
    with patch(
        "services.role_config.set_scope_roles",
        new_callable=AsyncMock,
        side_effect=RuntimeError("conflict"),
    ):
        response = _client(UserRole.MAINTAINERS).put("/jurisdictions/config", json=body)

    assert response.status_code == 409


# ── PUT /config/global/reorder (ADMINS) ─────────────────────────────────────


@pytest.mark.unit
def test_reorder_global_config_happy():
    body = {"role_order": ["Mayor", "Council Member"]}
    with patch(
        "services.role_config.reorder_roles", new_callable=AsyncMock
    ) as mock_reorder:
        response = _client(UserRole.ADMINS).put(
            "/jurisdictions/config/global/reorder", json=body
        )

    assert response.status_code == 200
    assert response.json()["data"] == {"ok": True}
    mock_reorder.assert_awaited_once()


@pytest.mark.unit
def test_reorder_global_config_forbidden_for_maintainer():
    body = {"role_order": ["Mayor"]}
    response = _client(UserRole.MAINTAINERS).put(
        "/jurisdictions/config/global/reorder", json=body
    )
    assert response.status_code == 403


# ── PUT /config/reorder (MAINTAINERS) ───────────────────────────────────────


@pytest.mark.unit
def test_reorder_jurisdiction_config_happy():
    body = {
        "ocdid": _OCDID,
        "scope": "locality",
        "role_order": ["Mayor", "Council Member"],
    }
    with patch(
        "services.role_config.reorder_roles", new_callable=AsyncMock
    ) as mock_reorder:
        response = _client(UserRole.MAINTAINERS).put(
            "/jurisdictions/config/reorder", json=body
        )

    assert response.status_code == 200
    assert response.json()["data"] == {"ok": True}
    mock_reorder.assert_awaited_once()


@pytest.mark.unit
def test_reorder_jurisdiction_config_set_mismatch_is_409():
    body = {"ocdid": _OCDID, "scope": "locality", "role_order": ["Mayor"]}
    with patch(
        "services.role_config.reorder_roles",
        new_callable=AsyncMock,
        side_effect=RuntimeError("Reorder set mismatch"),
    ):
        response = _client(UserRole.MAINTAINERS).put(
            "/jurisdictions/config/reorder", json=body
        )

    assert response.status_code == 409