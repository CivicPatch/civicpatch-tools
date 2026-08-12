import re
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
def test_suggest_returns_two_word_when_no_collision():
    with patch(
        "database.users.display_name_in_use",
        new_callable=AsyncMock,
        return_value=False,
    ) as mock_in_use:
        response = _client().get("/display-name/suggestion")

    assert response.status_code == 200
    name = response.json()["data"]
    assert re.fullmatch(r"[a-z]+-[a-z]+", name)
    mock_in_use.assert_awaited_once()


@pytest.mark.unit
def test_suggest_falls_back_to_three_word_on_first_collision():
    with patch(
        "database.users.display_name_in_use",
        new_callable=AsyncMock,
        side_effect=[True, False],
    ) as mock_in_use:
        response = _client().get("/display-name/suggestion")

    assert response.status_code == 200
    name = response.json()["data"]
    assert re.fullmatch(r"[a-z]+-[a-z]+-[a-z]+", name)
    assert mock_in_use.await_count == 2


@pytest.mark.unit
def test_suggest_appends_numeric_suffix_on_deep_collision():
    with patch(
        "database.users.display_name_in_use",
        new_callable=AsyncMock,
        side_effect=[True, True],
    ) as mock_in_use:
        response = _client().get("/display-name/suggestion")

    assert response.status_code == 200
    name = response.json()["data"]
    assert re.fullmatch(r"[a-z]+-[a-z]+-[a-z]+-\d{4}", name)
    assert mock_in_use.await_count == 2


@pytest.mark.unit
def test_save_happy_path():
    with patch(
        "database.users.set_user_display_name", new_callable=AsyncMock
    ) as mock_set:
        response = _client().post(
            "/display-name", json={"display_name": "apple-witch"}
        )

    assert response.status_code == 200
    assert response.json() == {"data": {"display_name": "apple-witch"}}
    mock_set.assert_awaited_once_with(
        "11111111-2222-3333-4444-555555555555", "apple-witch"
    )


@pytest.mark.unit
def test_save_strips_whitespace_before_writing():
    with patch(
        "database.users.set_user_display_name", new_callable=AsyncMock
    ) as mock_set:
        response = _client().post(
            "/display-name", json={"display_name": "  apple-witch  "}
        )

    assert response.status_code == 200
    call = mock_set.await_args
    assert call is not None
    assert call.args[1] == "apple-witch"


@pytest.mark.unit
def test_save_rejects_empty():
    response = _client().post("/display-name", json={"display_name": "   "})
    assert response.status_code == 400


@pytest.mark.unit
def test_save_rejects_too_long():
    response = _client().post(
        "/display-name", json={"display_name": "x" * 51}
    )
    assert response.status_code == 400


@pytest.mark.unit
def test_save_returns_409_on_unique_violation():
    with patch(
        "database.users.set_user_display_name",
        new_callable=AsyncMock,
        side_effect=UniqueViolation("duplicate"),
    ):
        response = _client().post(
            "/display-name", json={"display_name": "apple-witch"}
        )

    assert response.status_code == 409
