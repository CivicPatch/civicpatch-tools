"""HTTP-contract tests for API-key CRUD.

What matters here is who may do what: maintainers get keys of their own, and being a maintainer
is not power over anybody else's.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from lib.auth import get_optional_user
from routers.api import api_keys as api_keys_router
from schemas.api_keys import MAX_LABEL_LENGTH
from schemas.common import ApiKeyScope, Identity, UserRole

_PREFIX = "/api_keys"


def _identity(role: UserRole = UserRole.MAINTAINERS, user_id: str = "user-1") -> Identity:
    return Identity(
        type="cookie",
        provider="supabase",
        provider_user_id=user_id,
        email=f"{user_id}@example.com",
        role=role.value,
        user_id="00000000-0000-4000-8000-000000000001",
    )


def _client(identity: Identity | None = None) -> TestClient:
    app = FastAPI()
    app.dependency_overrides[get_optional_user] = lambda: identity or _identity()
    app.include_router(api_keys_router.get_router(), prefix=_PREFIX)
    return TestClient(app)


@pytest.mark.unit
def test_listing_shows_only_the_suffix():
    """The key itself is stored hashed, so a listing can never show it again."""
    with patch(
        "routers.api.api_keys.database.get_api_keys_for_user",
        new_callable=AsyncMock,
        return_value=[{"id": 1, "suffix": "ab12", "created_at": None, "revoked_at": None}],
    ):
        response = _client().get(_PREFIX)

    assert response.status_code == 200
    [key] = response.json()["data"]
    assert key["suffix"] == "ab12"
    assert "api_key" not in key


@pytest.mark.unit
def test_creating_returns_the_key_once():
    with patch(
        "routers.api.api_keys.database.create_api_key",
        new_callable=AsyncMock,
        return_value="cp_secret_ab12",
    ):
        response = _client().post(_PREFIX, json={"label": "Claude Code on laptop"})

    assert response.status_code == 200
    assert response.json()["api_key"] == "cp_secret_ab12"


@pytest.mark.unit
def test_a_new_key_is_an_agent_key_unless_asked():
    with patch(
        "routers.api.api_keys.database.create_api_key", new_callable=AsyncMock, return_value="cp_secret"
    ) as create:
        _client().post(_PREFIX, json={"label": "  Claude Code on laptop  "})

    create.assert_awaited_once_with("supabase", "user-1", ApiKeyScope.AGENT, "Claude Code on laptop")


@pytest.mark.unit
def test_a_full_key_is_an_explicit_choice():
    with patch(
        "routers.api.api_keys.database.create_api_key", new_callable=AsyncMock, return_value="cp_secret"
    ) as create:
        _client().post(_PREFIX, json={"label": "sheet push", "scope": "full"})

    create.assert_awaited_once_with("supabase", "user-1", ApiKeyScope.FULL, "sheet push")


@pytest.mark.unit
@pytest.mark.parametrize(
    "body",
    [{}, {"label": "   "}, {"label": "x" * (MAX_LABEL_LENGTH + 1)}, {"label": "ok", "scope": "admin"}],
)
def test_a_key_needs_a_label_and_a_known_scope(body: dict):
    with patch("routers.api.api_keys.database.create_api_key", new_callable=AsyncMock) as create:
        response = _client().post(_PREFIX, json=body)

    assert response.status_code == 422
    create.assert_not_awaited()


@pytest.mark.unit
def test_contributors_cannot_mint_a_key():
    """A key carries its owner's access, so minting one is a maintainer action."""
    response = _client(_identity(UserRole.CONTRIBUTORS)).post(_PREFIX, json={"label": "x"})
    assert response.status_code in (401, 403)


@pytest.mark.unit
def test_a_maintainer_cannot_revoke_someone_elses_key():
    """Being a maintainer grants keys of your own, not power over anybody else's."""
    with patch(
        "routers.api.api_keys.database.get_user_by_api_key_id",
        new_callable=AsyncMock,
        return_value={"provider": "supabase", "provider_user_id": "somebody-else"},
    ):
        response = _client().post(f"{_PREFIX}/7/revoke")

    assert response.status_code == 403


@pytest.mark.unit
def test_revoking_a_key_that_does_not_exist_is_a_404():
    with patch(
        "routers.api.api_keys.database.get_user_by_api_key_id",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = _client().post(f"{_PREFIX}/7/revoke")

    assert response.status_code == 404


@pytest.mark.unit
def test_a_key_cannot_be_deleted():
    """Revoked, never deleted: the row is the record that a leaked key existed."""
    methods = {
        method
        for route in api_keys_router.get_router().routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }
    assert "DELETE" not in methods
