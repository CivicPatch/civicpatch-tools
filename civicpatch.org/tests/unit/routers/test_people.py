import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from schemas.common import Identity, Role
from lib.auth import get_optional_user
from routers.api import people as people_router

MOCK_IDENTITY = Identity(
    type="service_api_key",
    provider="system",
    provider_user_id="test-user",
    email="test@civicpatch.org",
    teams=[Role.CONTRIBUTORS, Role.MAINTAINERS, Role.ADMINS, Role.DEFAULT],
)

TEST_OCDID = "ocd-jurisdiction/country:us/state:ca/place:oakland"


@pytest.fixture
def client():
    app = FastAPI()
    app.dependency_overrides[get_optional_user] = lambda: MOCK_IDENTITY
    app.include_router(people_router.get_router(), prefix="/people")
    return TestClient(app)


@pytest.mark.unit
def test_list_directory_returns_paginated_data(client):
    with patch(
        "database.people.get_all_people_for_jurisdiction",
        new_callable=AsyncMock,
        return_value=(2, [{"id": "p-1", "name": "Jane Doe"}, {"id": "p-2", "name": "John Smith"}]),
    ):
        response = client.get("/people/directory", params={"jurisdiction_ocdid": TEST_OCDID})

    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "total_items" in data
    assert data["total_items"] == 2
    assert len(data["data"]) == 2


@pytest.mark.unit
def test_list_directory_empty_returns_zero(client):
    with patch(
        "database.people.get_all_people_for_jurisdiction",
        new_callable=AsyncMock,
        return_value=(0, []),
    ):
        response = client.get("/people/directory", params={"jurisdiction_ocdid": TEST_OCDID})

    assert response.status_code == 200
    data = response.json()
    assert data["total_items"] == 0
    assert data["data"] == []


@pytest.mark.unit
def test_delete_person_returns_200(client):
    with patch(
        "database.people.delete_person",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = client.delete("/people/person-id-123")

    assert response.status_code == 200
    data = response.json()
    assert data["data"] is None


@pytest.mark.unit
def test_patch_people_data_records_change_log(client):
    """Publishing a manual edit records the diff in the change log
    (before = current canonical people, after = submitted data)."""
    ocdid = "ocd-jurisdiction/country:us/state:ca/place:oakland/government"
    submitted = [{"id": "p-1", "name": "Renamed Person"}]
    before = [{"id": "p-1", "name": "Original Person"}]
    record = AsyncMock()
    identity = Identity(
        type="session", provider="github", provider_user_id="u1",
        email="u@x.com", role=Role.CONTRIBUTORS, user_id="user-123",
    )
    client.app.dependency_overrides[get_optional_user] = lambda: identity
    with (
        patch("lib.github.pull_requests.open_attributed_pr", new_callable=AsyncMock,
              return_value=(42, "https://github.com/x/pull/42")),
        patch("database.people.get_people_by_jurisdiction_ocdid", new_callable=AsyncMock,
              return_value=before),
        patch("core.change_logs.record_manual_edits", record),
    ):
        response = client.patch(
            "/people/data",
            json={"jurisdiction_ocdid": ocdid, "data": submitted},
        )

    assert response.status_code == 200
    record.assert_awaited_once()
    _, logged_ocdid, user_id, before_arg, after_arg = record.await_args.args
    assert logged_ocdid == ocdid
    assert user_id == "user-123"
    assert before_arg == before
    assert after_arg == submitted
