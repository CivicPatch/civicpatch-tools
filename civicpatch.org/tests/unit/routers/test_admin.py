from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lib.auth import get_optional_user
from routers.api import admin as admin_router
from schemas.common import Identity, Role


ADMIN_IDENTITY = Identity(
    type="cookie",
    provider="supabase",
    provider_user_id="admin-uuid",
    email="admin@example.com",
    teams=[Role.ADMINS],
)

NON_ADMIN_IDENTITY = Identity(
    type="cookie",
    provider="supabase",
    provider_user_id="user-uuid",
    email="user@example.com",
    teams=[Role.CONTRIBUTORS],
)

TARGET_USER_ID = "11111111-2222-3333-4444-555555555555"


def _client(identity: Identity) -> TestClient:
    app = FastAPI()
    app.dependency_overrides[get_optional_user] = lambda: identity
    app.include_router(admin_router.get_router(), prefix="/api/admin")
    return TestClient(app)


@pytest.mark.unit
def test_list_users_happy_path():
    rows = [
        {
            "id": "uuid-1",
            "email": "alice@example.com",
            "display_name": "Alice",
            "provider": "supabase",
            "provider_user_id": "sb-1",
            "roles": ["admins"],
        },
    ]
    with patch(
        "database.users.list_users_with_roles", new_callable=AsyncMock, return_value=rows
    ):
        client = _client(ADMIN_IDENTITY)
        response = client.get("/api/admin/users")

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == [
        {
            "id": "uuid-1",
            "email": "alice@example.com",
            "display_name": "Alice",
            "provider": "supabase",
            "provider_user_id": "sb-1",
            "roles": ["admins"],
        },
    ]


@pytest.mark.unit
def test_list_users_forbidden_without_admins_role():
    client = _client(NON_ADMIN_IDENTITY)
    response = client.get("/api/admin/users")

    assert response.status_code == 403


@pytest.mark.unit
def test_set_user_roles_happy_path():
    user_row = {
        "id": TARGET_USER_ID,
        "provider": "supabase",
        "provider_user_id": "sb-target",
        "email": "target@example.com",
        "display_name": None,
    }
    with (
        patch(
            "database.users.get_user_by_id",
            new_callable=AsyncMock,
            return_value=user_row,
        ),
        patch("database.users.set_user_roles", new_callable=AsyncMock) as mock_set,
        patch(
            "lib.auth_session.invalidate_session", new_callable=AsyncMock
        ) as mock_invalidate,
    ):
        client = _client(ADMIN_IDENTITY)
        response = client.put(
            f"/api/admin/users/{TARGET_USER_ID}/roles",
            json={"roles": ["admins", "maintainers"]},
        )

    assert response.status_code == 200
    assert response.json() == {
        "data": {"id": TARGET_USER_ID, "roles": ["admins", "maintainers"]}
    }
    mock_set.assert_awaited_once_with(TARGET_USER_ID, ["admins", "maintainers"])
    mock_invalidate.assert_awaited_once_with("supabase", "sb-target")


@pytest.mark.unit
def test_set_user_roles_rejects_unknown_role():
    client = _client(ADMIN_IDENTITY)
    response = client.put(
        f"/api/admin/users/{TARGET_USER_ID}/roles",
        json={"roles": ["hacker"]},
    )

    assert response.status_code == 422


@pytest.mark.unit
def test_set_user_roles_returns_404_when_user_missing():
    with (
        patch(
            "database.users.get_user_by_id", new_callable=AsyncMock, return_value=None
        ),
        patch("database.users.set_user_roles", new_callable=AsyncMock) as mock_set,
        patch(
            "lib.auth_session.invalidate_session", new_callable=AsyncMock
        ) as mock_invalidate,
    ):
        client = _client(ADMIN_IDENTITY)
        response = client.put(
            f"/api/admin/users/{TARGET_USER_ID}/roles",
            json={"roles": ["admins"]},
        )

    assert response.status_code == 404
    mock_set.assert_not_awaited()
    mock_invalidate.assert_not_awaited()


@pytest.mark.unit
def test_set_user_roles_forbidden_without_admins_role():
    client = _client(NON_ADMIN_IDENTITY)
    response = client.put(
        f"/api/admin/users/{TARGET_USER_ID}/roles",
        json={"roles": ["admins"]},
    )

    assert response.status_code == 403


@pytest.mark.unit
def test_set_user_roles_rejects_self_edit_from_session_caller():
    self_admin = Identity(
        type="cookie",
        provider="supabase",
        provider_user_id="self-uuid",
        email="self@example.com",
        teams=[Role.ADMINS],
        user_id=TARGET_USER_ID,
    )
    with (
        patch("database.users.get_user_by_id", new_callable=AsyncMock) as mock_get,
        patch("database.users.set_user_roles", new_callable=AsyncMock) as mock_set,
        patch(
            "lib.auth_session.invalidate_session", new_callable=AsyncMock
        ) as mock_invalidate,
    ):
        client = _client(self_admin)
        response = client.put(
            f"/api/admin/users/{TARGET_USER_ID}/roles",
            json={"roles": []},
        )

    assert response.status_code == 403
    mock_get.assert_not_awaited()
    mock_set.assert_not_awaited()
    mock_invalidate.assert_not_awaited()


@pytest.mark.unit
def test_set_user_roles_allows_service_api_key_against_any_user():
    # SERVICE_API_KEY's synthetic Identity carries no user_id, so it can't trip
    # the self-edit check even when targeting an arbitrary user_id.
    service_identity = Identity(
        type="service_api_key",
        provider="system",
        provider_user_id="service_api_key",
        email="service@civicpatch.org",
        teams=[Role.ADMINS],
    )
    user_row = {
        "id": TARGET_USER_ID,
        "provider": "supabase",
        "provider_user_id": "sb-target",
        "email": "target@example.com",
        "display_name": None,
    }
    with (
        patch(
            "database.users.get_user_by_id",
            new_callable=AsyncMock,
            return_value=user_row,
        ),
        patch("database.users.set_user_roles", new_callable=AsyncMock) as mock_set,
        patch("lib.auth_session.invalidate_session", new_callable=AsyncMock),
    ):
        client = _client(service_identity)
        response = client.put(
            f"/api/admin/users/{TARGET_USER_ID}/roles",
            json={"roles": ["admins"]},
        )

    assert response.status_code == 200
    mock_set.assert_awaited_once_with(TARGET_USER_ID, ["admins"])
