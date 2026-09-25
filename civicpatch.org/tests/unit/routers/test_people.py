import pytest
from core.people_edits import PeopleValidationError
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


def _row(person_id: str, name: str) -> dict:
    """A row as `PERSON_JSON` builds one, narrowed. `jurisdiction_ocdid` is here because
    `as_people` validates against `Person`, which requires it — a bare `{"id", "name"}` no
    longer stands in for a person."""
    return {"id": person_id, "name": name, "jurisdiction_ocdid": TEST_OCDID}


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
@pytest.mark.unit
def test_the_public_read_stays_one_jurisdiction_and_unpaged(client):
    """It backs the public jurisdiction page, where a roster is eighteen people at most."""
    with patch(
        "routers.api.people.database.get_roster",
        new_callable=AsyncMock,
        return_value=[_row("1", "Ada Whitfield")],
    ) as get_roster:
        response = client.get(f"/people?jurisdiction_ocdid={TEST_OCDID}")

    assert response.status_code == 200
    [row] = response.json()["data"]
    assert (row["id"], row["name"]) == ("1", "Ada Whitfield")
    get_roster.assert_awaited_once_with(jurisdiction_ocdid=TEST_OCDID)


@pytest.mark.unit
def test_the_public_read_withholds_what_a_reader_is_not_owed(client):
    """`sightings` and `labels` are post-derivation input, declared server-owned in
    `core.people_edits.SERVER_OWNED_FIELDS`, and a membership's `meta_unmatched_text` is parser
    diagnostics. All three were on this public unpaged endpoint until 2026-09-24, because the
    route returned `PERSON_JSON`'s dicts and nothing filtered them. `Person` declares none of
    them, so answering with the model is the filter."""
    with patch(
        "routers.api.people.database.get_roster",
        new_callable=AsyncMock,
        return_value=[dict(_row("1", "Ada Whitfield"), sightings=[{"label": "Mayor"}], labels=["Mayor"])],
    ):
        response = client.get(f"/people?jurisdiction_ocdid={TEST_OCDID}")

    [row] = response.json()["data"]
    assert "sightings" not in row
    assert "labels" not in row


@pytest.mark.unit
def test_bulk_pages_a_whole_state(client):
    """One request per page instead of one per jurisdiction."""
    with patch(
        "routers.api.people.database.get_roster_page",
        new_callable=AsyncMock,
        return_value=(1416, [_row("1", "Ada Whitfield")]),
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


# ── who may read who edited what ─────────────────────────────────────────────


@pytest.mark.unit
def test_claims_are_keyed_by_person_for_the_roster(client):
    with (
        patch(
            "database.people.get_roster",
            new_callable=AsyncMock,
            return_value=[{"id": "p-1", "name": "Jane Doe"}],
        ),
        patch(
            "routers.api.people.claims_for_people",
            new_callable=AsyncMock,
            return_value={"p-1": [{"field_path": "phones", "kind": "accept"}]},
        ) as mock_claims,
    ):
        response = client.get("/people/claims", params={"jurisdiction_ocdid": TEST_OCDID})

    assert response.status_code == 200
    assert response.json()["data"]["p-1"][0]["field_path"] == "phones"
    mock_claims.assert_awaited_once_with(["p-1"])


@pytest.mark.unit
def test_claims_are_not_public_though_the_roster_beside_them_is(client):
    """The reason this is its own route. `GET /people` is public — "the public page's own
    data" — but an assertion carries `created_by_name`, so folding it in would tell an
    anonymous visitor who edited which field of which official."""
    client.app.dependency_overrides[get_optional_user] = lambda: None

    with patch("database.people.get_roster", new_callable=AsyncMock, return_value=[]):
        assert client.get(
            "/people/claims", params={"jurisdiction_ocdid": TEST_OCDID}
        ).status_code in (401, 403)
        # ...while the roster itself still answers.
        assert client.get(
            "/people", params={"jurisdiction_ocdid": TEST_OCDID}
        ).status_code == 200
