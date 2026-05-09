import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from psycopg.errors import UniqueViolation

from schemas.common import Identity, Role
from lib.auth import get_optional_user
from routers.api import review_sessions as review_sessions_router

MOCK_IDENTITY = Identity(
    type="service_api_key",
    provider="system",
    provider_user_id="test-user",
    email="test@civicpatch.org",
    teams=[Role.CONTRIBUTORS, Role.MAINTAINERS, Role.ADMINS, Role.DEFAULT],
    user_id="user-id-123",
)

TEST_SESSION_ID = "session-id-456"


@pytest.fixture
def client():
    app = FastAPI()
    app.dependency_overrides[get_optional_user] = lambda: MOCK_IDENTITY
    app.include_router(review_sessions_router.get_router(), prefix="/review-sessions")
    return TestClient(app)


@pytest.mark.unit
def test_get_review_stats_returns_cached(client):
    cached_stats = {"reviewed": 10, "remaining": 5}
    with patch(
        "lib.cache.get_cached",
        new_callable=AsyncMock,
        return_value=cached_stats,
    ):
        response = client.get("/review-sessions/stats", params={"state_code": "ca"})

    assert response.status_code == 200
    data = response.json()
    assert "data" in data


@pytest.mark.unit
def test_get_review_stats_fetches_from_db_on_cache_miss(client):
    db_stats = {"reviewed": 10, "remaining": 5}
    with (
        patch("lib.cache.get_cached", new_callable=AsyncMock, return_value=None),
        patch("database.review_session_stats.get_review_stats", new_callable=AsyncMock, return_value=db_stats),
        patch("lib.cache.set_cached", new_callable=AsyncMock),
    ):
        response = client.get("/review-sessions/stats", params={"state_code": "ca"})

    assert response.status_code == 200
    assert response.json()["data"] == db_stats


@pytest.mark.unit
def test_create_review_session_returns_session(client):
    session = {"id": TEST_SESSION_ID, "state_code": "ca", "status": "active"}
    with patch(
        "database.review_sessions.create_or_get_review_session",
        new_callable=AsyncMock,
        return_value=session,
    ):
        response = client.post(
            "/review-sessions",
            json={"state_code": "ca", "daily_goal": 20},
        )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert data["data"]["id"] == TEST_SESSION_ID


@pytest.mark.unit
def test_end_session_returns_200(client):
    with patch(
        "database.review_sessions.end_review_session",
        new_callable=AsyncMock,
    ):
        response = client.post(f"/review-sessions/{TEST_SESSION_ID}/end")

    assert response.status_code == 200
    assert response.json()["data"] is None


@pytest.mark.unit
def test_get_active_session_returns_null_when_none(client):
    with patch(
        "database.review_sessions.get_active_review_session",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = client.get("/review-sessions/active", params={"state_code": "tx"})

    assert response.status_code == 200
    assert response.json()["data"] is None


@pytest.mark.unit
def test_get_active_session_returns_session_when_active(client):
    active = {"session_id": TEST_SESSION_ID, "daily_goal": 10, "current_entry_number": 3}
    with patch(
        "database.review_sessions.get_active_review_session",
        new_callable=AsyncMock,
        return_value=active,
    ):
        response = client.get("/review-sessions/active", params={"state_code": "tx"})

    assert response.status_code == 200
    assert response.json()["data"]["session_id"] == TEST_SESSION_ID
    assert response.json()["data"]["current_entry_number"] == 3
