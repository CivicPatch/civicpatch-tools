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
    user_id="user-id-123",
)


def _user_at(role: Role) -> Identity:
    """Cookie-style identity at a specific trust level, for gate tests."""
    return Identity(
        type="cookie",
        provider="supabase",
        provider_user_id="sb-test",
        email="test@example.com",
        role=role.value,
        user_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    )


def _client_as(identity: Identity) -> TestClient:
    app = FastAPI()
    app.dependency_overrides[get_optional_user] = lambda: identity
    app.include_router(review_sessions_router.get_router(), prefix="/review-sessions")
    return TestClient(app)


TEST_SESSION_ID = "session-id-456"


@pytest.fixture
def client():
    app = FastAPI()
    app.dependency_overrides[get_optional_user] = lambda: MOCK_IDENTITY
    app.include_router(review_sessions_router.get_router(), prefix="/review-sessions")
    return TestClient(app)


@pytest.mark.unit
def test_get_review_stats_does_not_consult_cache(client):
    # available_count is read from a live pool and changes quickly. A cached
    # response previously masked new PRs (and stale-released claims) for up to
    # five minutes, surfacing as "1 available" when two were actually claimable.
    db_stats = {"reviewed": 10, "remaining": 5}
    with (
        patch("lib.cache.get_cached", new_callable=AsyncMock, return_value=None) as cache_get_mock,
        patch("lib.cache.set_cached", new_callable=AsyncMock) as cache_set_mock,
        patch("database.review_session_stats.get_review_stats", new_callable=AsyncMock, return_value=db_stats),
    ):
        response = client.get("/review-sessions/stats", params={"state_code": "ca"})

    assert response.status_code == 200
    cache_get_mock.assert_not_called()
    cache_set_mock.assert_not_called()


@pytest.mark.unit
def test_create_review_session_returns_session(client):
    session = {"id": TEST_SESSION_ID, "state_code": "ca"}
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
def test_navigate_to_done_auto_ends_session(client):
    # When navigation reports the session is exhausted ("done"), the route must
    # end the session so a later /active lookup can't resurrect it as resumable.
    with (
        patch(
            "database.review_session_navigation.navigate_to_entry",
            new_callable=AsyncMock,
            return_value={"done": "no_more_cards"},
        ),
        patch(
            "database.review_sessions.end_review_session",
            new_callable=AsyncMock,
        ) as end_mock,
    ):
        response = client.post(
            f"/review-sessions/{TEST_SESSION_ID}/navigate",
            json={"entry_number": 5},
        )

    assert response.status_code == 200
    body = response.json()
    assert body == {"data": None, "reason": "no_more_cards"}
    end_mock.assert_awaited_once_with(TEST_SESSION_ID)


@pytest.mark.unit
def test_get_active_session_returns_null_when_none(client):
    with patch(
        "database.review_sessions.get_active_review_session",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = client.get("/review-sessions/active?state_code=tx")

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
        response = client.get("/review-sessions/active?state_code=tx")

    assert response.status_code == 200
    assert response.json()["data"]["session_id"] == TEST_SESSION_ID
    assert response.json()["data"]["current_entry_number"] == 3


@pytest.mark.unit
def test_get_active_session_passes_state_code_to_db(client):
    # The state_code query param must be forwarded to the DB layer so that
    # state-scoped lookups actually scope by state.
    with patch(
        "database.review_sessions.get_active_review_session",
        new_callable=AsyncMock,
        return_value=None,
    ) as db_mock:
        response = client.get("/review-sessions/active?state_code=nj")

    assert response.status_code == 200
    args, _ = db_mock.call_args
    assert args[1] == "nj"


@pytest.mark.unit
def test_get_active_session_requires_state_code(client):
    # Missing state_code => FastAPI returns 422 (missing required query param).
    response = client.get("/review-sessions/active")
    assert response.status_code == 422


# ── Auth gates on write routes ──────────────────────────────────────────────
#
# These routes are RouteCategory.AUTHENTICATED: any signed-in user, including
# a default-level user with no elevation, may run a review session. The write
# routes must not 403 them.


@pytest.mark.unit
@pytest.mark.parametrize(
    "method,url,body",
    [
        ("post", "/review-sessions", {"state_code": "ca", "daily_goal": 5}),
        ("post", f"/review-sessions/{TEST_SESSION_ID}/navigate", {"entry_number": 1}),
        ("post", f"/review-sessions/{TEST_SESSION_ID}/pass", {"entry_number": 1}),
        ("post", f"/review-sessions/{TEST_SESSION_ID}/end", None),
    ],
)
def test_review_session_writes_allow_default_role(method, url, body):
    """Default-level signed-in users may run review sessions; the write routes
    must not 403 them."""
    client = _client_as(_user_at(Role.DEFAULT))
    kwargs = {"json": body} if body is not None else {}
    with (
        patch(
            "database.review_sessions.create_or_get_review_session",
            new_callable=AsyncMock,
            return_value={"id": TEST_SESSION_ID},
        ),
        patch(
            "database.review_session_entries.pass_entry",
            new_callable=AsyncMock,
        ),
        # navigate/pass short-circuit through the "done" branch so the heavy
        # downstream sync path doesn't need mocking.
        patch(
            "database.review_session_navigation.navigate_to_entry",
            new_callable=AsyncMock,
            return_value={"done": "no_more_cards"},
        ),
        patch(
            "database.review_sessions.end_review_session",
            new_callable=AsyncMock,
        ),
    ):
        response = getattr(client, method)(url, **kwargs)
    assert response.status_code == 200
