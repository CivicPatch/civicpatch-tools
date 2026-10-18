from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

import services.governing_law_source_pages as source_pages_service
from lib.auth import get_optional_user
from routers.api import governing_law_source_pages as source_pages_router
from schemas.common import Identity, UserRole
from services.governing_law_source_pages import (
    GoverningLawSourcePageText,
    NotPlainText,
    SourcePageNotFound,
    UnknownJurisdiction,
)
from shared.schemas import GoverningLawSourcePage

pytestmark = pytest.mark.unit

OCDID = "ocd-jurisdiction/country:us/state:vt/place:stowe/government"
URL = f"/jurisdictions/{OCDID}/governing_law_source_pages"
_SOURCE_URL = "https://legislature.vermont.gov/statutes/fullchapter/24APPENDIX/149"
_PAGE = GoverningLawSourcePage(
    id="row-1", jurisdiction_ocdid=OCDID, source_url=_SOURCE_URL, page_hash="abc", cache_path="governing_law/abc.md",
    collected_at=datetime(2026, 10, 18, tzinfo=timezone.utc),
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
    app.include_router(source_pages_router.get_router(), prefix="/jurisdictions")
    return TestClient(app)


def _post(client, identity, raises=None):
    client.app.dependency_overrides[get_optional_user] = identity
    with patch.object(source_pages_service, "store_source_page", new=AsyncMock(return_value=_PAGE, side_effect=raises)) as store:
        response = client.post(URL, json={"source_url": _SOURCE_URL, "text": "§ 1."})
    return response, store


def test_the_collector_stores_a_page_and_gets_its_row(client):
    response, store = _post(client, _service_key)

    assert response.status_code == 200, response.text
    assert response.json() == {"data": _PAGE.model_dump(mode="json")}
    store.assert_awaited_once_with(OCDID, _SOURCE_URL, "§ 1.")


def test_html_is_422_and_an_unknown_jurisdiction_404(client):
    assert _post(client, _service_key, raises=NotPlainText())[0].status_code == 422
    assert _post(client, _service_key, raises=UnknownJurisdiction(OCDID))[0].status_code == 404


def test_the_team_reads_a_page_back_and_a_missing_one_is_404(client):
    client.app.dependency_overrides[get_optional_user] = _contributor
    found = GoverningLawSourcePageText(page=_PAGE, text="§ 1.")
    with patch.object(source_pages_service, "read_source_page", new=AsyncMock(return_value=found)):
        assert client.get(f"{URL}/row-1").json() == {"data": {**_PAGE.model_dump(mode="json"), "text": "§ 1."}}
    with patch.object(source_pages_service, "read_source_page", new=AsyncMock(side_effect=SourcePageNotFound("x"))):
        assert client.get(f"{URL}/x").status_code == 404


def test_the_public_can_neither_store_nor_read(client):
    client.app.dependency_overrides[get_optional_user] = lambda: None
    assert client.post(URL, json={"source_url": _SOURCE_URL, "text": "§ 1."}).status_code == 403
    assert client.get(f"{URL}/row-1").status_code == 403
