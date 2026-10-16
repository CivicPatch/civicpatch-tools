import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

import services.government_form as government_form_service
from lib.auth import get_optional_user
from routers.api import government_forms as government_forms_router
from schemas.common import Identity, UserRole
from schemas.jurisdictions import JurisdictionDetailsFields
from shared.schemas import GovernmentForm

pytestmark = pytest.mark.unit

OCDID = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
URL = f"/jurisdictions/{OCDID}/government_form"
BODY = {"government_form": "mayor_council"}


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
    app.include_router(government_forms_router.get_router(), prefix="/jurisdictions")
    return TestClient(app)


def _put(client, identity, raises=None):
    client.app.dependency_overrides[get_optional_user] = identity
    details = JurisdictionDetailsFields(government_form=None, government_form_options=[], open_pull_request_url=None)
    with patch.object(
        government_form_service, "set_government_form", new=AsyncMock(side_effect=raises)
    ) as mock_set, patch.object(
        government_form_service, "fill_government_form", new=AsyncMock(side_effect=raises)
    ) as mock_fill, patch.object(
        government_form_service, "jurisdiction_details_fields", new=AsyncMock(return_value=details)
    ):
        response = client.put(URL, json=BODY)
    return response, mock_set, mock_fill


def test_a_maintainer_sets_the_form(client):
    response, mock_set, mock_fill = _put(client, _maintainer)

    assert response.status_code == 200, response.text
    mock_set.assert_awaited_once_with(OCDID, GovernmentForm.MAYOR_COUNCIL, "user-789")
    mock_fill.assert_not_awaited()


def test_the_pipeline_only_fills_it(client):
    response, mock_set, mock_fill = _put(client, _service_key)

    assert response.status_code == 200, response.text
    mock_fill.assert_awaited_once_with(OCDID, GovernmentForm.MAYOR_COUNCIL)
    mock_set.assert_not_awaited()


def test_a_contributor_cannot_set_it(client):
    response, mock_set, _ = _put(client, _contributor)

    assert response.status_code == 403
    mock_set.assert_not_awaited()


@pytest.mark.parametrize(
    "raised,status",
    [
        (government_form_service.UnknownJurisdiction(OCDID), 404),
        (government_form_service.GovernmentFormNotAtLevel("no"), 422),
        (government_form_service.GovernmentFormAlreadySet(OCDID), 409),
    ],
)
def test_a_refusal_becomes_its_status(client, raised, status):
    response, _, _ = _put(client, _service_key, raises=raised)

    assert response.status_code == status
