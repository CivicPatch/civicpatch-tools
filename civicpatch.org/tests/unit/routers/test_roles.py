"""Thin HTTP-contract tests for the role endpoints. Auth gating is exercised by
overriding get_optional_user per role; the service layer is mocked at the call
boundary.

The happy paths run full-stack in tests/integration/routers/test_roles.py — what
lives here is the per-role gating and the error mapping, which are cheap to
cover exhaustively with a mock and expensive to cover against a real DB.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from lib.auth import get_optional_user
from routers.api import roles as roles_router
from schemas.common import Identity, UserRole
from shared.schemas import Role

_PREFIX = "/roles"


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
    app.include_router(roles_router.get_router(), prefix=_PREFIX)
    return TestClient(app)


# ── GET /roles (open) ───────────────────────────────────────────────────


@pytest.mark.unit
def test_get_roles_happy():
    roles = [Role(id="mayor", label="Mayor", is_unique=False, aliases=["mayor"])]
    with patch(
        "services.role_config.load_roles", new_callable=AsyncMock, return_value=roles
    ):
        response = _client(UserRole.MAINTAINERS).get(_PREFIX)

    assert response.status_code == 200
    assert response.json()["data"]["roles"] == [
        {
            "id": "mayor",
            "label": "Mayor",
            "status": "active",
            "is_unique": False,
            "priority": None,
            "aliases": ["mayor"],
        }
    ]


@pytest.mark.unit
def test_get_roles_is_open_to_everyone():
    """The taxonomy is a vocabulary, and the jurisdiction page is public — it needs role
    labels to head a list of posts. Editing stays at maintainer."""
    roles = [Role(id="mayor", label="Mayor", is_unique=False, aliases=["mayor"])]
    with patch(
        "services.role_config.load_roles", new_callable=AsyncMock, return_value=roles
    ):
        response = _client(UserRole.CONTRIBUTORS).get(_PREFIX)

    assert response.status_code == 200


# ── PUT /roles (MAINTAINERS) ────────────────────────────────────────────


@pytest.mark.unit
def test_put_roles_happy_calls_set_roles():
    body = {"roles": [{"label": "Mayor"}]}
    with patch("services.role_config.set_roles", new_callable=AsyncMock) as mock_set:
        response = _client(UserRole.MAINTAINERS).put(_PREFIX, json=body)

    assert response.status_code == 200
    assert response.json()["data"] == {"ok": True}
    mock_set.assert_awaited_once()


@pytest.mark.unit
def test_put_roles_runtime_error_is_409():
    with patch(
        "services.role_config.set_roles",
        new_callable=AsyncMock,
        side_effect=RuntimeError("conflict"),
    ):
        response = _client(UserRole.MAINTAINERS).put(_PREFIX, json={"roles": []})

    assert response.status_code == 409


@pytest.mark.unit
def test_put_roles_forbidden_below_maintainer():
    response = _client(UserRole.CONTRIBUTORS).put(_PREFIX, json={"roles": []})
    assert response.status_code == 403


# ── PUT /roles/reorder (ADMINS) ─────────────────────────────────────────


@pytest.mark.unit
def test_reorder_happy():
    body = {"role_order": ["Mayor", "Council Member"]}
    with patch(
        "services.role_config.reorder_roles", new_callable=AsyncMock
    ) as mock_reorder:
        response = _client(UserRole.ADMINS).put(f"{_PREFIX}/reorder", json=body)

    assert response.status_code == 200
    assert response.json()["data"] == {"ok": True}
    mock_reorder.assert_awaited_once()


@pytest.mark.unit
def test_reorder_forbidden_for_maintainer():
    body = {"role_order": ["Mayor"]}
    response = _client(UserRole.MAINTAINERS).put(f"{_PREFIX}/reorder", json=body)
    assert response.status_code == 403


@pytest.mark.unit
def test_reorder_set_mismatch_is_409():
    with patch(
        "services.role_config.reorder_roles",
        new_callable=AsyncMock,
        side_effect=RuntimeError("Reorder set mismatch"),
    ):
        response = _client(UserRole.ADMINS).put(
            f"{_PREFIX}/reorder", json={"role_order": ["Mayor"]}
        )

    assert response.status_code == 409


# ── DELETE /roles/{role_id} (MAINTAINERS) ───────────────────────────────


@pytest.mark.unit
def test_delete_role_happy():
    with patch(
        "services.role_config.deactivate_role", new_callable=AsyncMock, return_value=True
    ) as mock_deactivate:
        response = _client(UserRole.MAINTAINERS).delete(f"{_PREFIX}/mayor")

    assert response.status_code == 200
    assert response.json()["data"] == {"ok": True}
    mock_deactivate.assert_awaited_once()


@pytest.mark.unit
def test_delete_unknown_role_is_404():
    """The service returns False both for "no such role" and "already
    inactive"; the route maps that single signal to 404."""
    with patch(
        "services.role_config.deactivate_role",
        new_callable=AsyncMock,
        return_value=False,
    ):
        response = _client(UserRole.MAINTAINERS).delete(f"{_PREFIX}/nope")

    assert response.status_code == 404


@pytest.mark.unit
def test_delete_role_forbidden_below_maintainer():
    assert _client(UserRole.CONTRIBUTORS).delete(f"{_PREFIX}/mayor").status_code == 403
