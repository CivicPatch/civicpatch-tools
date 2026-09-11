from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lib.auth import get_optional_user
from routers.api import admin as admin_router
from schemas.common import Identity, UserRole
from schemas.rollback import RollbackCandidate
from services import rollback


ADMIN_IDENTITY = Identity(
    type="cookie",
    provider="supabase",
    provider_user_id="admin-uuid",
    email="admin@example.com",
    role=UserRole.ADMINS.value,
)

NON_ADMIN_IDENTITY = Identity(
    type="cookie",
    provider="supabase",
    provider_user_id="user-uuid",
    email="user@example.com",
    role=UserRole.CONTRIBUTORS.value,
)

TARGET_USER_ID = "11111111-2222-3333-4444-555555555555"

# `ADMIN_IDENTITY` above carries no `user_id` (unused by every other route here), but a
# rollback needs one to attribute the withdrawal to — a session/cookie identity always has one.
ADMIN_WITH_USER_ID = ADMIN_IDENTITY.model_copy(update={"user_id": "admin-user-id"})


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
            "username": "Alice",
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
            "username": "Alice",
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
        "username": "target-user",
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
        role=UserRole.ADMINS.value,
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
        "username": "target-user",
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


# ── Get one user ─────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_get_user_happy_path():
    user_row = {
        "id": TARGET_USER_ID,
        "email": "target@example.com",
        "username": "Target User",
        "provider": "supabase",
        "provider_user_id": "sb-target",
        "role": "maintainers",
        "last_login_at": None,
    }
    with patch(
        "database.users.get_user_by_id", new_callable=AsyncMock, return_value=user_row
    ):
        client = _client(ADMIN_IDENTITY)
        response = client.get(f"/api/admin/users/{TARGET_USER_ID}")

    assert response.status_code == 200
    assert response.json()["data"] == user_row


@pytest.mark.unit
def test_get_user_returns_404_when_missing():
    with patch(
        "database.users.get_user_by_id", new_callable=AsyncMock, return_value=None
    ):
        client = _client(ADMIN_IDENTITY)
        response = client.get(f"/api/admin/users/{TARGET_USER_ID}")

    assert response.status_code == 404


@pytest.mark.unit
def test_get_user_forbidden_without_admins_role():
    client = _client(NON_ADMIN_IDENTITY)
    response = client.get(f"/api/admin/users/{TARGET_USER_ID}")

    assert response.status_code == 403


# ── Rollback ─────────────────────────────────────────────────────────────────

_CANDIDATE = RollbackCandidate(
    assertion_id="assertion-1",
    entity_id="person-1",
    entity_label="Ada M. Chen",
    field_path="name",
    kind="accept",
    value="Ada M. Chen",
    jurisdiction_ocdid="ocd-jurisdiction/country:us/state:zz/place:x/government",
    status="active",
    created_at="2026-09-10T12:00:00+00:00",
)


@pytest.mark.unit
def test_list_user_assertions_happy_path():
    with patch(
        "services.rollback.list_user_assertions",
        new_callable=AsyncMock,
        return_value=[_CANDIDATE],
    ) as mock_list:
        client = _client(ADMIN_WITH_USER_ID)
        response = client.get(f"/api/admin/users/{TARGET_USER_ID}/rollback-candidates")

    assert response.status_code == 200
    assert response.json() == {"data": [_CANDIDATE.model_dump(mode="json")]}
    mock_list.assert_awaited_once_with(TARGET_USER_ID)


@pytest.mark.unit
def test_list_user_assertions_forbidden_without_admins_role():
    client = _client(NON_ADMIN_IDENTITY)
    response = client.get(f"/api/admin/users/{TARGET_USER_ID}/rollback-candidates")

    assert response.status_code == 403


@pytest.mark.unit
def test_rollback_user_happy_path():
    with (
        patch(
            "services.rollback.list_user_assertions",
            new_callable=AsyncMock,
            return_value=[_CANDIDATE],
        ),
        patch(
            "services.rollback.rollback_assertions",
            new_callable=AsyncMock,
            return_value=1,
        ) as mock_rollback,
    ):
        client = _client(ADMIN_WITH_USER_ID)
        response = client.post(
            f"/api/admin/users/{TARGET_USER_ID}/rollback",
            json={"assertion_ids": [_CANDIDATE.assertion_id]},
        )

    assert response.status_code == 200
    assert response.json() == {"data": {"withdrawn": 1}}
    mock_rollback.assert_awaited_once_with(
        [_CANDIDATE.assertion_id], ADMIN_WITH_USER_ID.user_id, None
    )


@pytest.mark.unit
def test_rollback_user_filters_out_ids_not_belonging_to_the_user():
    with (
        patch(
            "services.rollback.list_user_assertions",
            new_callable=AsyncMock,
            return_value=[_CANDIDATE],
        ),
        patch(
            "services.rollback.rollback_assertions",
            new_callable=AsyncMock,
            return_value=1,
        ) as mock_rollback,
    ):
        client = _client(ADMIN_WITH_USER_ID)
        response = client.post(
            f"/api/admin/users/{TARGET_USER_ID}/rollback",
            json={"assertion_ids": [_CANDIDATE.assertion_id, "not-theirs"]},
        )

    assert response.status_code == 200
    mock_rollback.assert_awaited_once_with(
        [_CANDIDATE.assertion_id], ADMIN_WITH_USER_ID.user_id, None
    )


@pytest.mark.unit
def test_rollback_user_returns_409_when_nothing_to_roll_back():
    with (
        patch(
            "services.rollback.list_user_assertions",
            new_callable=AsyncMock,
            return_value=[_CANDIDATE],
        ),
        patch(
            "services.rollback.rollback_assertions",
            new_callable=AsyncMock,
            side_effect=rollback.NothingToRollBack([_CANDIDATE.assertion_id]),
        ),
    ):
        client = _client(ADMIN_WITH_USER_ID)
        response = client.post(
            f"/api/admin/users/{TARGET_USER_ID}/rollback",
            json={"assertion_ids": [_CANDIDATE.assertion_id]},
        )

    assert response.status_code == 409


@pytest.mark.unit
def test_rollback_user_rejects_empty_assertion_ids():
    client = _client(ADMIN_WITH_USER_ID)
    response = client.post(
        f"/api/admin/users/{TARGET_USER_ID}/rollback",
        json={"assertion_ids": []},
    )

    assert response.status_code == 422


@pytest.mark.unit
def test_rollback_user_forbidden_without_admins_role():
    rollback_mock = AsyncMock()
    with patch("services.rollback.rollback_assertions", rollback_mock):
        client = _client(NON_ADMIN_IDENTITY)
        response = client.post(
            f"/api/admin/users/{TARGET_USER_ID}/rollback",
            json={"assertion_ids": [_CANDIDATE.assertion_id]},
        )

    assert response.status_code == 403
    rollback_mock.assert_not_awaited()
