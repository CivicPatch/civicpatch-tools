import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from schemas.common import Identity, Role
from lib.auth import get_optional_user
from routers.api import leaderboard as leaderboard_router

MOCK_IDENTITY = Identity(
    type="service_api_key",
    provider="system",
    provider_user_id="test-user",
    email="test@civicpatch.org",
    teams=[Role.DEFAULT],
    user_id="user-id-123",
)

MOCK_ENTRIES = [
    {"state_code": "ca", "display_name": "alice_reviews", "provider": "github", "provider_user_id": "seed-1", "resolved_count": 142},
    {"state_code": "ny", "display_name": "bob_patch", "provider": "github", "provider_user_id": "seed-2", "resolved_count": 38},
]


@pytest.fixture
def client():
    app = FastAPI()
    app.dependency_overrides[get_optional_user] = lambda: MOCK_IDENTITY
    app.include_router(leaderboard_router.get_router(), prefix="/leaderboard")
    return TestClient(app)


@pytest.mark.unit
def test_get_leaderboard_returns_cached(client):
    cached = {"entries": MOCK_ENTRIES}
    with patch("lib.cache.get_cached", new_callable=AsyncMock, return_value=cached):
        response = client.get("/leaderboard")

    assert response.status_code == 200
    data = response.json()
    assert data["data"] == cached


@pytest.mark.unit
def test_get_leaderboard_fetches_from_db_on_cache_miss(client):
    with (
        patch("lib.cache.get_cached", new_callable=AsyncMock, return_value=None),
        patch(
            "database.review_sessions.get_leaderboard",
            new_callable=AsyncMock,
            return_value=MOCK_ENTRIES,
        ),
        patch("lib.cache.set_cached", new_callable=AsyncMock),
    ):
        response = client.get("/leaderboard")

    assert response.status_code == 200
    assert response.json()["data"]["entries"] == MOCK_ENTRIES


@pytest.mark.unit
def test_get_leaderboard_writes_cache_on_db_fetch(client):
    mock_set_cached = AsyncMock()
    with (
        patch("lib.cache.get_cached", new_callable=AsyncMock, return_value=None),
        patch(
            "database.review_sessions.get_leaderboard",
            new_callable=AsyncMock,
            return_value=MOCK_ENTRIES,
        ),
        patch("lib.cache.set_cached", mock_set_cached),
    ):
        client.get("/leaderboard")

    mock_set_cached.assert_called_once()
    args = mock_set_cached.call_args
    assert args[0][0] == "leaderboard_data"
    assert args[0][1]["entries"] == MOCK_ENTRIES
