"""Thin HTTP-contract tests for the role endpoints. Auth gating is exercised by
overriding get_optional_user per role; the service layer is mocked at the call
boundary.

The read runs full-stack in tests/integration/routers/test_roles.py; writes open
an open-data pull request, so what lives here is the per-role gating and the
error mapping.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from lib.auth import get_optional_user
from routers.api import roles as roles_router
from schemas.common import Identity, UserRole
from shared.schemas import Role

from core.role_config_edits import RoleConfigEditRefused
from services.role_config_pull_request import (
    OpenedRoleConfigPullRequest,
    RoleConfigPullRequestAlreadyOpen,
    RoleConfigPullRequestFailed,
)

_PREFIX = "/roles"
_OPEN = "services.role_config_pull_request.open_role_config_pull_request"
_OPENED = OpenedRoleConfigPullRequest(
    pull_request_number=12, pull_request_url="https://github.com/civicpatch/open-data/pull/12"
)


def _identity(role: UserRole) -> Identity:
    return Identity(
        type="cookie",
        provider="supabase",
        provider_user_id="user-uuid",
        email="user@example.com",
        role=role.value,
        user_id="user-1",
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
            "selection_method": "elected_by_voters",
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


# ── POST /roles, PUT /roles/{role_id} (MAINTAINERS) ─────────────────────


@pytest.mark.unit
def test_add_role_returns_the_opened_pull_request():
    with patch(_OPEN, new_callable=AsyncMock, return_value=_OPENED) as mock_open:
        response = _client(UserRole.MAINTAINERS).post(_PREFIX, json={"label": "Mayor"})

    assert response.status_code == 200
    assert response.json()["data"] == {
        "pull_request_number": 12,
        "pull_request_url": "https://github.com/civicpatch/open-data/pull/12",
    }
    mock_open.assert_awaited_once()


@pytest.mark.unit
def test_edit_role_returns_the_opened_pull_request():
    with patch(_OPEN, new_callable=AsyncMock, return_value=_OPENED) as mock_open:
        response = _client(UserRole.MAINTAINERS).put(f"{_PREFIX}/mayor", json={"label": "Mayor"})

    assert response.status_code == 200
    assert response.json()["data"]["pull_request_number"] == 12
    mock_open.assert_awaited_once()


@pytest.mark.unit
def test_refused_edit_is_409():
    with patch(_OPEN, new_callable=AsyncMock, side_effect=RoleConfigEditRefused("Nothing to change.")):
        response = _client(UserRole.MAINTAINERS).put(f"{_PREFIX}/mayor", json={"label": "Mayor"})

    assert response.status_code == 409
    assert response.json() == {"error": "Nothing to change."}


@pytest.mark.unit
def test_change_while_one_is_open_is_409_with_its_url():
    url = "https://github.com/civicpatch/open-data/pull/11"
    with patch(_OPEN, new_callable=AsyncMock, side_effect=RoleConfigPullRequestAlreadyOpen(url)):
        response = _client(UserRole.MAINTAINERS).post(_PREFIX, json={"label": "Mayor"})

    assert response.status_code == 409
    assert response.json()["pull_request_url"] == url


@pytest.mark.unit
def test_github_failure_is_502():
    with patch(_OPEN, new_callable=AsyncMock, side_effect=RoleConfigPullRequestFailed("no branch")):
        response = _client(UserRole.MAINTAINERS).post(_PREFIX, json={"label": "Mayor"})

    assert response.status_code == 502


@pytest.mark.unit
def test_add_and_edit_forbidden_below_maintainer():
    client = _client(UserRole.CONTRIBUTORS)
    assert client.post(_PREFIX, json={"label": "Mayor"}).status_code == 403
    assert client.put(f"{_PREFIX}/mayor", json={"label": "Mayor"}).status_code == 403


# ── PUT /roles/reorder (ADMINS) ─────────────────────────────────────────


@pytest.mark.unit
def test_reorder_returns_the_opened_pull_request():
    with patch(_OPEN, new_callable=AsyncMock, return_value=_OPENED) as mock_open:
        response = _client(UserRole.ADMINS).put(f"{_PREFIX}/reorder", json={"role_order": ["mayor"]})

    assert response.status_code == 200
    assert response.json()["data"]["pull_request_number"] == 12
    mock_open.assert_awaited_once()


@pytest.mark.unit
def test_reorder_forbidden_for_maintainer():
    response = _client(UserRole.MAINTAINERS).put(f"{_PREFIX}/reorder", json={"role_order": ["mayor"]})
    assert response.status_code == 403


# ── DELETE /roles/{role_id} (MAINTAINERS) ───────────────────────────────


@pytest.mark.unit
def test_delete_role_returns_the_opened_pull_request():
    with patch(_OPEN, new_callable=AsyncMock, return_value=_OPENED) as mock_open:
        response = _client(UserRole.MAINTAINERS).delete(f"{_PREFIX}/mayor")

    assert response.status_code == 200
    assert response.json()["data"]["pull_request_number"] == 12
    mock_open.assert_awaited_once()


@pytest.mark.unit
def test_delete_role_forbidden_below_maintainer():
    assert _client(UserRole.CONTRIBUTORS).delete(f"{_PREFIX}/mayor").status_code == 403
