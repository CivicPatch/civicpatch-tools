from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import lib.supabase_auth as supabase_auth_service
from lib.auth import get_optional_user
from routers.api import admin as admin_router
from schemas.common import Identity, Role


ADMIN_IDENTITY = Identity(
    type="cookie",
    provider="supabase",
    provider_user_id="admin-uuid",
    email="admin@example.com",
    role=Role.ADMINS.value,
)

NON_ADMIN_IDENTITY = Identity(
    type="cookie",
    provider="supabase",
    provider_user_id="user-uuid",
    email="user@example.com",
    role=Role.CONTRIBUTORS.value,
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
            "role": "admins",
            "last_login_at": "2024-06-01T12:00:00+00:00",
        },
    ]
    with patch(
        "database.users.list_users", new_callable=AsyncMock, return_value=rows
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
            "role": "admins",
            "last_login_at": "2024-06-01T12:00:00+00:00",
        },
    ]


@pytest.mark.unit
def test_list_users_forbidden_without_admins_role():
    client = _client(NON_ADMIN_IDENTITY)
    response = client.get("/api/admin/users")

    assert response.status_code == 403


@pytest.mark.unit
def test_set_user_role_happy_path():
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
        patch("database.users.set_user_role", new_callable=AsyncMock) as mock_set,
        patch(
            "lib.auth_session.invalidate_session", new_callable=AsyncMock
        ) as mock_invalidate,
    ):
        client = _client(ADMIN_IDENTITY)
        response = client.put(
            f"/api/admin/users/{TARGET_USER_ID}/role",
            json={"role": "maintainers"},
        )

    assert response.status_code == 200
    assert response.json() == {"data": {"id": TARGET_USER_ID, "role": "maintainers"}}
    mock_set.assert_awaited_once_with(TARGET_USER_ID, "maintainers")
    mock_invalidate.assert_awaited_once_with("supabase", "sb-target")


@pytest.mark.unit
def test_set_user_role_rejects_unknown_role():
    client = _client(ADMIN_IDENTITY)
    response = client.put(
        f"/api/admin/users/{TARGET_USER_ID}/role",
        json={"role": "hacker"},
    )

    assert response.status_code == 422


@pytest.mark.unit
def test_set_user_role_returns_404_when_user_missing():
    with (
        patch(
            "database.users.get_user_by_id", new_callable=AsyncMock, return_value=None
        ),
        patch("database.users.set_user_role", new_callable=AsyncMock) as mock_set,
        patch(
            "lib.auth_session.invalidate_session", new_callable=AsyncMock
        ) as mock_invalidate,
    ):
        client = _client(ADMIN_IDENTITY)
        response = client.put(
            f"/api/admin/users/{TARGET_USER_ID}/role",
            json={"role": "admins"},
        )

    assert response.status_code == 404
    mock_set.assert_not_awaited()
    mock_invalidate.assert_not_awaited()


@pytest.mark.unit
def test_set_user_role_forbidden_without_admins_role():
    client = _client(NON_ADMIN_IDENTITY)
    response = client.put(
        f"/api/admin/users/{TARGET_USER_ID}/role",
        json={"role": "admins"},
    )

    assert response.status_code == 403


@pytest.mark.unit
def test_set_user_role_rejects_self_edit_from_session_caller():
    self_admin = Identity(
        type="cookie",
        provider="supabase",
        provider_user_id="self-uuid",
        email="self@example.com",
        role=Role.ADMINS.value,
        user_id=TARGET_USER_ID,
    )
    with (
        patch("database.users.get_user_by_id", new_callable=AsyncMock) as mock_get,
        patch("database.users.set_user_role", new_callable=AsyncMock) as mock_set,
        patch(
            "lib.auth_session.invalidate_session", new_callable=AsyncMock
        ) as mock_invalidate,
    ):
        client = _client(self_admin)
        response = client.put(
            f"/api/admin/users/{TARGET_USER_ID}/role",
            json={"role": "default"},
        )

    assert response.status_code == 403
    mock_get.assert_not_awaited()
    mock_set.assert_not_awaited()
    mock_invalidate.assert_not_awaited()


@pytest.mark.unit
def test_set_user_role_allows_service_api_key_against_any_user():
    # SERVICE_API_KEY's synthetic Identity carries no user_id, so it can't trip
    # the self-edit check even when targeting an arbitrary user_id.
    service_identity = Identity(
        type="service_api_key",
        provider="system",
        provider_user_id="service_api_key",
        email="service@civicpatch.org",
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
        patch("database.users.set_user_role", new_callable=AsyncMock) as mock_set,
        patch("lib.auth_session.invalidate_session", new_callable=AsyncMock),
    ):
        client = _client(service_identity)
        response = client.put(
            f"/api/admin/users/{TARGET_USER_ID}/role",
            json={"role": "admins"},
        )

    assert response.status_code == 200
    mock_set.assert_awaited_once_with(TARGET_USER_ID, "admins")


def _client_with_supabase(
    identity: Identity,
    *,
    invite_mock: AsyncMock | None = None,
    list_users_mock: AsyncMock | None = None,
    get_user_by_id_mock: AsyncMock | None = None,
    delete_user_mock: AsyncMock | None = None,
) -> TestClient:
    """Like _client but injects a fake Supabase client whose auth.admin methods
    are the provided AsyncMocks. Pass only the methods the test needs."""
    app = FastAPI()
    fake_admin = SimpleNamespace(
        invite_user_by_email=invite_mock or AsyncMock(),
        list_users=list_users_mock or AsyncMock(return_value=[]),
        get_user_by_id=get_user_by_id_mock or AsyncMock(),
        delete_user=delete_user_mock or AsyncMock(),
    )
    fake_supabase = SimpleNamespace(auth=SimpleNamespace(admin=fake_admin))
    app.dependency_overrides[get_optional_user] = lambda: identity
    app.dependency_overrides[supabase_auth_service.get_supabase_admin_client] = lambda: fake_supabase
    app.include_router(admin_router.get_router(), prefix="/api/admin")
    return TestClient(app)


@pytest.mark.unit
def test_invite_user_happy_path():
    invite = AsyncMock(return_value=None)
    client = _client_with_supabase(ADMIN_IDENTITY, invite_mock=invite)
    response = client.post("/api/admin/users/invite", json={"email": "new@example.com"})

    assert response.status_code == 200
    assert response.json() == {"data": {"sent": True}}
    invite.assert_awaited_once_with("new@example.com")


@pytest.mark.unit
def test_invite_user_returns_409_when_email_already_registered():
    invite = AsyncMock(side_effect=Exception("User already registered"))
    client = _client_with_supabase(ADMIN_IDENTITY, invite_mock=invite)
    response = client.post("/api/admin/users/invite", json={"email": "existing@example.com"})

    assert response.status_code == 409
    assert response.json()["detail"] == "User already exists"


@pytest.mark.unit
def test_invite_user_returns_400_on_other_supabase_error():
    invite = AsyncMock(side_effect=Exception("rate limited"))
    client = _client_with_supabase(ADMIN_IDENTITY, invite_mock=invite)
    response = client.post("/api/admin/users/invite", json={"email": "new@example.com"})

    assert response.status_code == 400


@pytest.mark.unit
def test_invite_user_forbidden_without_admins_role():
    invite = AsyncMock()
    client = _client_with_supabase(NON_ADMIN_IDENTITY, invite_mock=invite)
    response = client.post("/api/admin/users/invite", json={"email": "new@example.com"})

    assert response.status_code == 403
    invite.assert_not_awaited()


# ── Pending invites ──────────────────────────────────────────────────────────


class _FakeSupabaseUser:
    def __init__(self, id, email, invited_at, last_sign_in_at):
        self.id = id
        self.email = email
        self.invited_at = invited_at
        self.last_sign_in_at = last_sign_in_at


@pytest.mark.unit
def test_list_pending_invites_filters_to_invited_only():
    from datetime import datetime, timezone
    invited_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    users = [
        # Pending: invited, never signed in → should be returned
        _FakeSupabaseUser("p-1", "pending@example.com", invited_at, None),
        # Accepted: invited AND signed in → should be filtered out
        _FakeSupabaseUser("a-1", "accepted@example.com", invited_at, datetime(2024, 1, 2, tzinfo=timezone.utc)),
        # Direct signup: no invited_at → should be filtered out
        _FakeSupabaseUser("d-1", "direct@example.com", None, datetime(2024, 1, 3, tzinfo=timezone.utc)),
    ]
    list_users = AsyncMock(return_value=users)
    client = _client_with_supabase(ADMIN_IDENTITY, list_users_mock=list_users)
    response = client.get("/api/admin/users/pending")

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["id"] == "p-1"
    assert data[0]["email"] == "pending@example.com"
    assert data[0]["invited_at"] == invited_at.isoformat()


@pytest.mark.unit
def test_list_pending_invites_forbidden_without_admins_role():
    list_users = AsyncMock(return_value=[])
    client = _client_with_supabase(NON_ADMIN_IDENTITY, list_users_mock=list_users)
    response = client.get("/api/admin/users/pending")

    assert response.status_code == 403
    list_users.assert_not_awaited()


# ── Resend invite ────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_resend_invite_happy_path():
    user_obj = _FakeSupabaseUser("u-1", "pending@example.com", None, None)
    get_user = AsyncMock(return_value=SimpleNamespace(user=user_obj))
    invite = AsyncMock(return_value=None)
    client = _client_with_supabase(
        ADMIN_IDENTITY, invite_mock=invite, get_user_by_id_mock=get_user
    )
    response = client.post(f"/api/admin/users/{TARGET_USER_ID}/resend-invite")

    assert response.status_code == 200
    assert response.json() == {"data": {"sent": True}}
    invite.assert_awaited_once_with("pending@example.com")


@pytest.mark.unit
def test_resend_invite_returns_404_when_user_missing():
    get_user = AsyncMock(side_effect=Exception("User not found"))
    client = _client_with_supabase(ADMIN_IDENTITY, get_user_by_id_mock=get_user)
    response = client.post(f"/api/admin/users/{TARGET_USER_ID}/resend-invite")

    assert response.status_code == 404


@pytest.mark.unit
def test_resend_invite_forbidden_without_admins_role():
    client = _client_with_supabase(NON_ADMIN_IDENTITY)
    response = client.post(f"/api/admin/users/{TARGET_USER_ID}/resend-invite")

    assert response.status_code == 403


# ── Revoke invite ────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_revoke_invite_happy_path():
    delete = AsyncMock(return_value=None)
    client = _client_with_supabase(ADMIN_IDENTITY, delete_user_mock=delete)
    response = client.delete(f"/api/admin/users/{TARGET_USER_ID}/invite")

    assert response.status_code == 200
    assert response.json() == {"data": {"revoked": True}}
    delete.assert_awaited_once_with(TARGET_USER_ID)


@pytest.mark.unit
def test_revoke_invite_forbidden_without_admins_role():
    delete = AsyncMock()
    client = _client_with_supabase(NON_ADMIN_IDENTITY, delete_user_mock=delete)
    response = client.delete(f"/api/admin/users/{TARGET_USER_ID}/invite")

    assert response.status_code == 403
    delete.assert_not_awaited()
