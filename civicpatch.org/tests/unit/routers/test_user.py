from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg.errors import UniqueViolation

from lib.auth import get_user
from routers.api import user as user_router
from schemas.common import Identity, UserRole


USER_IDENTITY = Identity(
    type="cookie",
    provider="supabase",
    provider_user_id="user-uuid",
    email="alice@example.com",
    role=UserRole.CONTRIBUTORS.value,
    user_id="11111111-2222-3333-4444-555555555555",
)


def _client(identity: Identity = USER_IDENTITY) -> TestClient:
    app = FastAPI()
    app.dependency_overrides[get_user] = lambda: identity
    app.include_router(user_router.get_router())
    return TestClient(app)


@pytest.mark.unit
def test_save_happy_path():
    with patch(
        "database.users.set_username", new_callable=AsyncMock
    ) as mock_set:
        response = _client().post(
            "/username", json={"username": "apple-witch"}
        )

    assert response.status_code == 200
    assert response.json() == {"data": {"username": "apple-witch"}}
    mock_set.assert_awaited_once_with(
        "11111111-2222-3333-4444-555555555555", "apple-witch"
    )


@pytest.mark.unit
def test_save_strips_whitespace_before_writing():
    with patch(
        "database.users.set_username", new_callable=AsyncMock
    ) as mock_set:
        response = _client().post(
            "/username", json={"username": "  apple-witch  "}
        )

    assert response.status_code == 200
    call = mock_set.await_args
    assert call is not None
    assert call.args[1] == "apple-witch"


@pytest.mark.unit
def test_save_rejects_empty():
    response = _client().post("/username", json={"username": "   "})
    assert response.status_code == 422


@pytest.mark.unit
def test_save_rejects_too_long():
    response = _client().post(
        "/username", json={"username": "x" * 51}
    )
    assert response.status_code == 422


@pytest.mark.unit
def test_save_rejects_a_space():
    response = _client().post("/username", json={"username": "apple witch"})
    assert response.status_code == 422


@pytest.mark.unit
def test_save_allows_dots_underscores_and_hyphens():
    with patch(
        "database.users.set_username", new_callable=AsyncMock
    ) as mock_set:
        response = _client().post(
            "/username", json={"username": "apple_witch-9.dev"}
        )

    assert response.status_code == 200
    mock_set.assert_awaited_once_with(
        "11111111-2222-3333-4444-555555555555", "apple_witch-9.dev"
    )


@pytest.mark.unit
def test_save_returns_409_on_unique_violation():
    with patch(
        "database.users.set_username",
        new_callable=AsyncMock,
        side_effect=UniqueViolation("duplicate"),
    ):
        response = _client().post(
            "/username", json={"username": "apple-witch"}
        )

    assert response.status_code == 409
