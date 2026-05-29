from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lib.supabase_auth import get_supabase_client
from routers import sso as sso_router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(sso_router.get_router(is_production=False), prefix="/api/v1/auth")
    # Override the Supabase client dependency with a mock; the real client is
    # only constructed in main.py's lifespan, which isn't used in these tests.
    app.dependency_overrides[get_supabase_client] = lambda: MagicMock()
    return TestClient(app)





def _client_with_supabase(app_supabase_mock):
    """Build a TestClient with the Supabase client dependency overridden."""
    app = FastAPI()
    app.include_router(sso_router.get_router(is_production=False), prefix="/api/v1/auth")
    app.dependency_overrides[get_supabase_client] = lambda: app_supabase_mock
    return TestClient(app)


@pytest.mark.unit
def test_request_otp_happy_path():
    supabase_mock = MagicMock()
    supabase_mock.auth.sign_in_with_otp = AsyncMock(return_value=MagicMock())
    tc = _client_with_supabase(supabase_mock)

    response = tc.post("/api/v1/auth/supabase/request-otp", json={"email": "a@example.com"})

    assert response.status_code == 200
    assert response.json() == {"data": {"sent": True}}
    supabase_mock.auth.sign_in_with_otp.assert_awaited_once_with(
        {"email": "a@example.com", "options": {"should_create_user": True}}
    )


@pytest.mark.unit
def test_request_otp_propagates_supabase_error_as_400():
    supabase_mock = MagicMock()
    supabase_mock.auth.sign_in_with_otp = AsyncMock(side_effect=RuntimeError("rate limited"))
    tc = _client_with_supabase(supabase_mock)

    response = tc.post("/api/v1/auth/supabase/request-otp", json={"email": "a@example.com"})

    assert response.status_code == 400
    assert "rate limited" in response.json()["detail"]


@pytest.mark.unit
def test_request_otp_rejects_missing_email(client):
    response = client.post("/api/v1/auth/supabase/request-otp", json={})
    assert response.status_code == 422


@pytest.mark.unit
def test_verify_otp_happy_path_mints_session():
    supabase_user = MagicMock()
    supabase_user.id = "user-uuid"
    supabase_user.email = "alice@example.com"
    supabase_user.user_metadata = {"full_name": "Alice"}
    auth_response = MagicMock(user=supabase_user)

    supabase_mock = MagicMock()
    supabase_mock.auth.verify_otp = AsyncMock(return_value=auth_response)
    tc = _client_with_supabase(supabase_mock)

    with (
        patch("database.users.upsert_user", new_callable=AsyncMock, return_value="u") as mock_upsert,
        patch("lib.auth_session.create_session_cookies", new_callable=AsyncMock) as mock_cookies,
    ):
        response = tc.post(
            "/api/v1/auth/supabase/verify-otp",
            json={"email": "alice@example.com", "code": "123456"},
        )

    assert response.status_code == 200
    assert response.json() == {"data": {"authenticated": True}}
    supabase_mock.auth.verify_otp.assert_awaited_once_with(
        {"email": "alice@example.com", "token": "123456", "type": "email"}
    )
    mock_upsert.assert_awaited_once_with("supabase", "user-uuid", "alice@example.com")
    mock_cookies.assert_awaited_once()


@pytest.mark.unit
def test_verify_otp_returns_401_when_supabase_raises():
    supabase_mock = MagicMock()
    supabase_mock.auth.verify_otp = AsyncMock(side_effect=RuntimeError("invalid OTP"))
    tc = _client_with_supabase(supabase_mock)

    response = tc.post(
        "/api/v1/auth/supabase/verify-otp",
        json={"email": "a@example.com", "code": "000000"},
    )

    assert response.status_code == 401
    assert "invalid OTP" in response.json()["detail"]


@pytest.mark.unit
def test_verify_otp_returns_401_when_no_user_in_response():
    supabase_mock = MagicMock()
    supabase_mock.auth.verify_otp = AsyncMock(return_value=MagicMock(user=None))
    tc = _client_with_supabase(supabase_mock)

    response = tc.post(
        "/api/v1/auth/supabase/verify-otp",
        json={"email": "a@example.com", "code": "123456"},
    )

    assert response.status_code == 401


@pytest.mark.unit
def test_verify_otp_rejects_missing_fields(client):
    r1 = client.post("/api/v1/auth/supabase/verify-otp", json={"email": "a@example.com"})
    r2 = client.post("/api/v1/auth/supabase/verify-otp", json={"code": "123456"})
    assert r1.status_code == 422
    assert r2.status_code == 422
