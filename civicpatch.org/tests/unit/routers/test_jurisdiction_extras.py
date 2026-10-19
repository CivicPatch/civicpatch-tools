"""`PATCH /api/v1/jurisdictions/{ocdid}`: cp.org's own fields, one permission rule for all of them."""

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

import services.extras_organizations as extras_organizations_service
import services.government_form as government_form_service
import services.jurisdiction_extras as jurisdiction_extras_service
from lib.auth import get_optional_user
from routers.api import jurisdictions as jurisdictions_router
from schemas.common import Identity, UserRole
from schemas.jurisdictions import JurisdictionDetailsFields
from shared.schemas import FoundBy, GoverningLaw, GoverningLawKind, GovernmentForm

pytestmark = pytest.mark.unit

OCDID = "ocd-jurisdiction/country:us/state:tn/place:nashville/government"
URL = f"/jurisdictions/{OCDID}"
ORGANIZATIONS = {
    "organizations": [{
        "name": "Metropolitan Council",
        "posts": [{
            "role": "vice-mayor", "label": "Vice Mayor",
            "extras": {"selection_method": "elected_by_voters"},
            "sources": [{"url": "https://example.gov/charter", "note": "The vice mayor shall be elected", "extras": {"source_page_id": "p1"}}],
        }],
    }],
    "extras": {"governing_law_collected_at": "2026-10-19T00:00:00Z"},
}
GOVERNING_LAW = GoverningLaw(
    kind=GoverningLawKind.CHARTER, classification=None, found_by=FoundBy.SEARCH,
    collected_at=datetime(2026, 10, 19, tzinfo=timezone.utc), cost_usd=None,
)


def _person(role: UserRole):
    return lambda: Identity(
        type="session", provider="github", provider_user_id="u3", email="m@x.com", role=role, user_id="user-789"
    )


def _service_key():
    return Identity(type="service_api_key", provider="system", provider_user_id="service_api_key", email=None)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(jurisdictions_router.get_router(), prefix="/jurisdictions")
    return TestClient(app)


def _patch(client, identity, body, raises=None):
    client.app.dependency_overrides[get_optional_user] = identity
    details = JurisdictionDetailsFields(
        government_form=None, government_form_options=[], open_pull_request_url=None,
        extras_government_form=None, extras_governing_law=None, extras_organizations=None,
    )
    with patch.object(
        jurisdiction_extras_service, "save_jurisdiction_extras", new=AsyncMock(side_effect=raises)
    ) as mock_save, patch.object(
        government_form_service, "jurisdiction_details_fields", new=AsyncMock(return_value=details)
    ):
        response = client.patch(URL, json=body)
    return response, mock_save


def _saved(mock_save):
    [(jurisdiction_ocdid, extras, user_id)] = [call.args for call in mock_save.await_args_list]
    return jurisdiction_ocdid, extras, user_id


def test_the_service_key_saves_the_organizations(client):
    response, mock_save = _patch(client, _service_key, {"extras_organizations": ORGANIZATIONS})

    assert response.status_code == 200, response.text
    _, extras, user_id = _saved(mock_save)
    assert (extras.extras_organizations.selection_methods(), user_id) == ({"vice-mayor": "elected_by_voters"}, None)


def test_a_maintainer_saves_the_government_form_as_themselves(client):
    response, mock_save = _patch(client, _person(UserRole.MAINTAINERS), {"extras_government_form": "mayor_council"})

    assert response.status_code == 200, response.text
    jurisdiction_ocdid, extras, user_id = _saved(mock_save)
    assert (jurisdiction_ocdid, extras.extras_government_form, user_id) == (OCDID, GovernmentForm.MAYOR_COUNCIL, "user-789")


def test_a_maintainers_governing_law_is_recorded_as_found_by_them(client):
    body = {"extras_governing_law": GOVERNING_LAW.model_dump(mode="json")}

    _, mock_save = _patch(client, _person(UserRole.MAINTAINERS), body)

    assert _saved(mock_save)[1].extras_governing_law.found_by == FoundBy.MAINTAINER


def test_a_contributor_cannot_edit(client):
    response, mock_save = _patch(client, _person(UserRole.CONTRIBUTORS), {"extras_government_form": "mayor_council"})

    assert response.status_code == 403
    mock_save.assert_not_awaited()


@pytest.mark.parametrize("body", [{}, {"extras_government_form": None}, {"population": 5}])
def test_an_empty_null_or_unknown_field_is_refused(client, body):
    response, mock_save = _patch(client, _service_key, body)

    assert response.status_code == 422
    mock_save.assert_not_awaited()


@pytest.mark.parametrize(
    "raised,status",
    [
        (government_form_service.UnknownJurisdiction(OCDID), 404),
        (extras_organizations_service.UnknownJurisdiction(OCDID), 404),
        (government_form_service.GovernmentFormNotAtLevel("no"), 422),
        (extras_organizations_service.UnknownRole("collector-of-taxes"), 422),
    ],
)
def test_a_refusal_becomes_its_status(client, raised, status):
    response, _ = _patch(client, _service_key, {"extras_government_form": "mayor_council"}, raises=raised)

    assert response.status_code == status
