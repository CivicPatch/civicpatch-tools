from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lib.supabase_auth import SupabaseUser
from routers import sso as sso_router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(sso_router.get_router(is_production=False), prefix="/api/v1/auth")
    return TestClient(app)


@pytest.mark.unit
def test_supabase_callback_happy_path_mints_session(client):
    fake_user = SupabaseUser(id="user-uuid", email="alice@example.com", display_name="Alice")

    with (
        patch("lib.supabase_auth.get_supabase_client", return_value=MagicMock()),
        patch("lib.supabase_auth.verify_jwt", new_callable=AsyncMock, return_value=fake_user),
        patch("database.users.upsert_user", new_callable=AsyncMock, return_value="new-user-uuid") as mock_upsert_user,
        patch("lib.auth_session.create_session_cookies", new_callable=AsyncMock) as mock_create_cookies,
    ):
        response = client.post(
            "/api/v1/auth/supabase/callback",
            json={"access_token": "valid.jwt.token"},
        )

    assert response.status_code == 200
    assert response.json() == {"data": {"authenticated": True}}
    # Justification per CLAUDE.md test-change rule: This test verified create_update_user was
    # called with empty teams. It now verifies upsert_user is called and no role-mutation
    # happens, because the Supabase callback no longer manages roles — that responsibility
    # moves to the future admin UI.
    mock_upsert_user.assert_awaited_once_with(
        "supabase", "user-uuid", "alice@example.com", "Alice"
    )
    mock_create_cookies.assert_awaited_once()


@pytest.mark.unit
def test_supabase_callback_returns_401_on_invalid_jwt(client):
    with (
        patch("lib.supabase_auth.get_supabase_client", return_value=MagicMock()),
        patch(
            "lib.supabase_auth.verify_jwt",
            new_callable=AsyncMock,
            side_effect=ValueError("Invalid Supabase JWT"),
        ),
    ):
        response = client.post(
            "/api/v1/auth/supabase/callback",
            json={"access_token": "bad.jwt"},
        )

    assert response.status_code == 401
    assert "Invalid Supabase JWT" in response.json()["detail"]


@pytest.mark.unit
def test_supabase_callback_rejects_missing_access_token(client):
    response = client.post("/api/v1/auth/supabase/callback", json={})
    assert response.status_code == 422
