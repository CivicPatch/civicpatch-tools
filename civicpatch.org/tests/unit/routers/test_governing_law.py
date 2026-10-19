import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

import services.governing_law as governing_law_service
from lib.auth import get_optional_user
from routers.api import governing_law as governing_law_router
from schemas.common import Identity, UserRole
from shared.schemas import FoundBy, GoverningLaw, GoverningLawKind

pytestmark = pytest.mark.unit

OCDID = "ocd-jurisdiction/country:us/state:vt/place:stowe/government"
URL = f"/jurisdictions/{OCDID}/governing_law"
BODY = {
    "kind": "charter",
    "classification": "town",
    "found_by": "state_index",
    "source_page_ids": ["5d3e2c6a-0c4b-4b8e-9a2d-1f6e7c8b9a01"],
    "collected_at": "2026-10-18T12:00:00Z",
    "cost_usd": None,
}


def _maintainer():
    return Identity(
        type="session", provider="github", provider_user_id="u3",
        email="m@x.com", role=UserRole.MAINTAINERS, user_id="user-789",
    )


def _contributor():
    return Identity(
        type="session", provider="github", provider_user_id="u4",
        email="c@x.com", role=UserRole.CONTRIBUTORS, user_id="user-321",
    )


def _service_key():
    return Identity(type="service_api_key", provider="system", provider_user_id="service_api_key", email=None)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(governing_law_router.get_router(), prefix="/jurisdictions")
    return TestClient(app)


def _put(client, identity, raises=None):
    client.app.dependency_overrides[get_optional_user] = identity
    with patch.object(governing_law_service, "set_governing_law", new=AsyncMock(side_effect=raises)) as mock_set:
        response = client.put(URL, json=BODY)
    return response, mock_set


def test_a_maintainer_sets_it_as_themselves(client):
    response, mock_set = _put(client, _maintainer)

    assert response.status_code == 200, response.text
    by_hand = GoverningLaw.model_validate({**BODY, "found_by": "maintainer"})
    mock_set.assert_awaited_once_with(OCDID, by_hand, "user-789")
    assert response.json()["data"]["found_by"] == "maintainer"


def test_the_collector_sets_it_as_nobody(client):
    response, mock_set = _put(client, _service_key)

    assert response.status_code == 200, response.text
    mock_set.assert_awaited_once_with(OCDID, GoverningLaw.model_validate(BODY), None)


def test_a_contributor_cannot_set_it(client):
    response, mock_set = _put(client, _contributor)

    assert response.status_code == 403
    mock_set.assert_not_awaited()


def test_an_unknown_jurisdiction_is_404(client):
    response, _ = _put(client, _maintainer, raises=governing_law_service.UnknownJurisdiction(OCDID))

    assert response.status_code == 404


def test_a_body_off_the_contract_is_422(client):
    client.app.dependency_overrides[get_optional_user] = _maintainer
    with patch.object(governing_law_service, "set_governing_law", new=AsyncMock()) as mock_set:
        response = client.put(URL, json={**BODY, "kind": "bylaws"})

    assert response.status_code == 422
    mock_set.assert_not_awaited()


_NONE_FOUND = GoverningLaw(
    kind=GoverningLawKind.NONE_FOUND, classification=None, found_by=FoundBy.STATE_INDEX,
    collected_at="2026-10-18T12:00:00Z", cost_usd=None,
)


def _get(client, identity, found):
    client.app.dependency_overrides[get_optional_user] = identity
    with patch.object(governing_law_service, "get_governing_law", new=AsyncMock(return_value=found)):
        return client.get(URL)


def test_the_team_and_the_collector_read_what_was_found_or_null(client):
    assert _get(client, _contributor, _NONE_FOUND).json()["data"]["kind"] == "none_found"
    assert _get(client, _service_key, None).json()["data"] is None


def test_the_public_cannot_read_it(client):
    assert _get(client, lambda: None, _NONE_FOUND).status_code == 403
