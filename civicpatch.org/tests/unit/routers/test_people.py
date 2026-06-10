import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from schemas.common import Identity, Role
from lib.auth import get_optional_user
from routers.api import people as people_router
from shared.utils.yaml_utils import yaml_dump

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


# An Official-valid person on `main`, in on-disk order; a patch overlays the edited fields.
BASE_PERSON = {
    "name": "Original Person",
    "phones": [],
    "emails": [],
    "urls": [],
    "office": {"name": "Mayor", "division_ocdid": None},
    "jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:ca/place:oakland/government",
    "source_urls": [],
    "updated_at": "2025-11-18T19:49:42+00:00",
    "id": "p-1",
}


def _contributor():
    return Identity(
        type="session", provider="github", provider_user_id="u1",
        email="u@x.com", role=Role.CONTRIBUTORS, user_id="user-123",
    )


def _default():
    return Identity(
        type="session", provider="github", provider_user_id="u2",
        email="d@x.com", role=Role.DEFAULT, user_id="user-456",
    )


@pytest.mark.unit
def test_patch_people_data_records_change_log(client):
    # This test previously verified before = DB canonical, after = the full submitted data.
    # It now verifies before = the `main` file we patched, after = the patched result —
    # because the endpoint moved to the patch model (overlay edits onto the main file).
    ocdid = BASE_PERSON["jurisdiction_ocdid"]
    record = AsyncMock()
    client.app.dependency_overrides[get_optional_user] = _contributor
    with (
        patch("lib.github.pull_requests.open_attributed_pr", new_callable=AsyncMock,
              return_value=(42, "https://github.com/x/pull/42")),
        patch("lib.github.api.get_github_file_contents", new_callable=AsyncMock,
              return_value=yaml_dump([BASE_PERSON])),
        patch("core.change_logs.record_manual_edits", record),
    ):
        response = client.patch(
            "/people/data",
            json={"jurisdiction_ocdid": ocdid, "data": [{"id": "p-1", "fields": {"name": "Renamed Person"}}]},
        )

    assert response.status_code == 200
    record.assert_awaited_once()
    _, logged_ocdid, user_id, before_arg, after_arg = record.await_args.args
    assert logged_ocdid == ocdid
    assert user_id == "user-123"
    assert [p["name"] for p in before_arg] == ["Original Person"]
    assert [p["name"] for p in after_arg] == ["Renamed Person"]


@pytest.mark.unit
def test_patch_people_data_rejects_invalid_field(client):
    client.app.dependency_overrides[get_optional_user] = _contributor
    with (
        patch("lib.github.pull_requests.open_attributed_pr", new_callable=AsyncMock) as mock_pr,
        patch("lib.github.api.get_github_file_contents", new_callable=AsyncMock,
              return_value=yaml_dump([BASE_PERSON])),
        patch("core.change_logs.record_manual_edits", new_callable=AsyncMock),
    ):
        response = client.patch(
            "/people/data",
            json={
                "jurisdiction_ocdid": BASE_PERSON["jurisdiction_ocdid"],
                "data": [{"id": "p-1", "fields": {"phones": ["not-a-phone"]}}],
            },
        )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail[0]["id"] == "p-1"
    assert detail[0]["name"] == "Original Person"
    assert detail[0]["field"] == "phones"
    mock_pr.assert_not_awaited()


@pytest.mark.unit
def test_patch_people_data_allows_default_role(client):
    # Default-role reviewers may open a manual-edit PR; the route is AUTHENTICATED,
    # not contributor-gated.
    client.app.dependency_overrides[get_optional_user] = _default
    with (
        patch("lib.github.pull_requests.open_attributed_pr", new_callable=AsyncMock,
              return_value=(42, "https://github.com/x/pull/42")),
        patch("lib.github.api.get_github_file_contents", new_callable=AsyncMock,
              return_value=yaml_dump([BASE_PERSON])),
        patch("core.change_logs.record_manual_edits", new_callable=AsyncMock),
    ):
        response = client.patch(
            "/people/data",
            json={"jurisdiction_ocdid": BASE_PERSON["jurisdiction_ocdid"],
                  "data": [{"id": "p-1", "fields": {"name": "Renamed Person"}}]},
        )

    assert response.status_code == 200
