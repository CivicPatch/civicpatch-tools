import pytest
from core.people_edits import PeopleValidationError
import services.roster_edits as roster_edits
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from schemas.common import Identity, UserRole
from lib.auth import get_optional_user
from routers.api import people as people_router
from shared.utils.yaml_utils import yaml_dump

MOCK_IDENTITY = Identity(
    type="service_api_key",
    provider="system",
    provider_user_id="test-user",
    email="test@civicpatch.org",
    teams=[UserRole.CONTRIBUTORS, UserRole.MAINTAINERS, UserRole.ADMINS, UserRole.DEFAULT],
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
        "database.people.get_people_page",
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
        "database.people.get_people_page",
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
    "source_urls": ["https://x.gov/council"],
    "updated_at": "2025-11-18T19:49:42+00:00",
    "id": "p-1",
}


def _contributor():
    return Identity(
        type="session", provider="github", provider_user_id="u1",
        email="u@x.com", role=UserRole.CONTRIBUTORS, user_id="user-123",
    )


def _default():
    return Identity(
        type="session", provider="github", provider_user_id="u2",
        email="d@x.com", role=UserRole.DEFAULT, user_id="user-456",
    )


def _maintainer():
    return Identity(
        type="session", provider="github", provider_user_id="u3",
        email="m@x.com", role=UserRole.MAINTAINERS, user_id="user-789",
    )


@pytest.mark.unit
def test_patch_people_data_returns_the_request_it_recorded(client):
    """Thin, on purpose. The endpoint used to read and write the open-data file itself, so its
    tests mocked GitHub; it now hands the whole edit to `roster_edits.edit_published`, which
    writes the database and queues the commit. What is left here is the HTTP contract."""
    ocdid = BASE_PERSON["jurisdiction_ocdid"]
    client.app.dependency_overrides[get_optional_user] = _maintainer
    edit = AsyncMock(return_value=("req-1", [BASE_PERSON]))
    with patch("services.roster_edits.edit_published", edit):
        response = client.patch(
            "/people/data",
            json={"jurisdiction_ocdid": ocdid, "data": [{"id": "p-1", "fields": {"name": "Renamed Person"}}]},
        )

    assert response.status_code == 200
    assert response.json()["data"] == {"changeset_id": "req-1"}
    edit.assert_awaited_once()
    assert edit.await_args.args[0] == ocdid


@pytest.mark.unit
def test_patch_people_data_rejects_invalid_field(client):
    """422 carrying which field failed, so the editor can mark the row rather than the person."""
    client.app.dependency_overrides[get_optional_user] = _maintainer
    with patch(
        "services.roster_edits.edit_published",
        AsyncMock(side_effect=PeopleValidationError(
            [{"id": "p-1", "name": "Original Person", "field": "phones",
              "message": "Invalid phone number: 'not-a-phone'"}]
        )),
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
    assert detail[0]["field"] == "phones"


@pytest.mark.unit
def test_patch_people_data_refuses_to_empty_a_jurisdiction(client):
    """An edit removing everybody would retire the whole roster. 409, not a silent wipe."""
    client.app.dependency_overrides[get_optional_user] = _maintainer
    with patch(
        "services.roster_edits.edit_published",
        AsyncMock(side_effect=roster_edits.EmptyEdit("x")),
    ):
        response = client.patch(
            "/people/data",
            json={"jurisdiction_ocdid": BASE_PERSON["jurisdiction_ocdid"], "data": []},
        )
    assert response.status_code == 409


@pytest.mark.unit
@pytest.mark.parametrize("identity", [_default, _contributor])
def test_patch_people_data_requires_maintainer(client, identity):
    # Editing published people (the jurisdiction page's Current tab) commits straight to
    # `main`, so it is gated to maintainers. Reviewing a scrape is a separate route and
    # stays AUTHENTICATED.
    client.app.dependency_overrides[get_optional_user] = identity
    with patch("lib.github.api.upsert_github_file", new_callable=AsyncMock) as mock_commit:
        response = client.patch(
            "/people/data",
            json={"jurisdiction_ocdid": BASE_PERSON["jurisdiction_ocdid"],
                  "data": [{"id": "p-1", "fields": {"name": "Renamed Person"}}]},
        )

    assert response.status_code == 403
    mock_commit.assert_not_awaited()


@pytest.mark.unit
def test_the_public_read_stays_one_jurisdiction_and_unpaged(client):
    """It backs the public jurisdiction page, where a roster is eighteen people at most."""
    with patch(
        "routers.api.people.database.get_roster",
        new_callable=AsyncMock,
        return_value=[{"id": "1", "name": "Ada Whitfield"}],
    ) as get_roster:
        response = client.get(f"/people?jurisdiction_ocdid={TEST_OCDID}")

    assert response.status_code == 200
    assert response.json() == {"data": [{"id": "1", "name": "Ada Whitfield"}]}
    get_roster.assert_awaited_once_with(jurisdiction_ocdid=TEST_OCDID)


@pytest.mark.unit
def test_bulk_pages_a_whole_state(client):
    """One request per page instead of one per jurisdiction."""
    with patch(
        "routers.api.people.database.get_roster_page",
        new_callable=AsyncMock,
        return_value=(1416, [{"id": "1", "name": "Ada Whitfield"}]),
    ) as get_roster_page:
        response = client.get("/people/bulk?state=WA&page=2&per_page=200")

    body = response.json()
    assert response.status_code == 200
    assert body["total_items"] == 1416
    assert body["total_pages"] == 8
    # Lowercased for the ocdid LIKE, and the offset follows the page.
    get_roster_page.assert_awaited_once_with(None, "wa", 200, 200)


@pytest.mark.unit
def test_bulk_refuses_a_state_that_is_not_a_code(client):
    """It reaches a LIKE against the ocdid, so it is worth rejecting before the query."""
    response = client.get("/people/bulk?state=washington")
    assert response.status_code == 400


@pytest.mark.unit
def test_bulk_requires_a_state(client):
    """Without one this would be every person in the database."""
    assert client.get("/people/bulk").status_code == 422
