"""HTTP-contract tests for connected apps: maintainers list and disconnect their own approvals."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lib.auth import get_optional_user
from lib.supabase_oauth import SupabaseAuthError
from routers.api import connected_apps as connected_apps_router
from schemas.common import Identity, UserRole
from schemas.connected_apps import ConnectedApp

_PREFIX = "/connected-apps"
_CLIENT_ID = "1e2c2d5d-e8c9-4a46-b6d4-6eab46d2653e"
_APP = ConnectedApp(client_id=_CLIENT_ID, name="ChatGPT", granted_at="2026-10-24T03:01:04Z")


def _identity(role: UserRole = UserRole.MAINTAINERS) -> Identity:
    return Identity(
        type="cookie", provider="supabase", provider_user_id="sb-user-1",
        email="user@example.com", role=role.value, user_id="00000000-0000-4000-8000-000000000001",
    )


def _client(identity: Identity) -> TestClient:
    app = FastAPI()
    app.dependency_overrides[get_optional_user] = lambda: identity
    app.include_router(connected_apps_router.get_router(), prefix=_PREFIX)
    return TestClient(app)


def _env():
    return patch.object(connected_apps_router.environment, "supabase_url_and_secret_key", return_value=("http://sb", "secret"))


@pytest.mark.unit
def test_a_maintainer_lists_their_connected_apps():
    with _env(), patch.object(connected_apps_router.service, "fetch_connected_apps", AsyncMock(return_value=[_APP])) as get:
        response = _client(_identity()).get(_PREFIX)

    assert response.status_code == 200
    assert response.json() == {"data": [_APP.model_dump()]}
    get.assert_awaited_once_with("http://sb", "secret", "sb-user-1")


@pytest.mark.unit
def test_a_contributor_cannot_list_or_disconnect():
    client = _client(_identity(UserRole.CONTRIBUTORS))

    assert client.get(_PREFIX).status_code == 403
    assert client.delete(f"{_PREFIX}/{_CLIENT_ID}").status_code == 403


@pytest.mark.unit
def test_disconnecting_revokes_the_app_for_the_caller():
    with _env(), patch.object(connected_apps_router.service, "disconnect_app", AsyncMock()) as disconnect:
        response = _client(_identity()).delete(f"{_PREFIX}/{_CLIENT_ID}")

    assert response.json() == {"data": {"disconnected": True}}
    disconnect.assert_awaited_once_with("http://sb", "secret", "sb-user-1", _CLIENT_ID)


@pytest.mark.unit
def test_a_client_id_that_is_not_a_uuid_is_refused_before_supabase():
    with patch.object(connected_apps_router.service, "disconnect_app", AsyncMock()) as disconnect:
        response = _client(_identity()).delete(f"{_PREFIX}/not-an-id")

    assert response.status_code == 422
    disconnect.assert_not_awaited()


@pytest.mark.unit
def test_disconnecting_an_app_that_is_not_connected_is_404():
    refused = AsyncMock(side_effect=SupabaseAuthError("grant not found", 404))
    with _env(), patch.object(connected_apps_router.service, "disconnect_app", refused):
        response = _client(_identity()).delete(f"{_PREFIX}/{_CLIENT_ID}")

    assert response.status_code == 404


@pytest.mark.unit
def test_any_other_supabase_failure_is_a_bad_gateway_not_the_callers_fault():
    failed = AsyncMock(side_effect=SupabaseAuthError("invalid JWT", 401))
    with (
        _env(),
        patch.object(connected_apps_router.service, "disconnect_app", failed),
        patch.object(connected_apps_router.service, "fetch_connected_apps", failed),
    ):
        client = _client(_identity())
        assert client.delete(f"{_PREFIX}/{_CLIENT_ID}").status_code == 502
        assert client.get(_PREFIX).status_code == 502
