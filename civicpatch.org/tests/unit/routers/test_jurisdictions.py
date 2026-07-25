import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from schemas.common import Identity, Role
from lib.auth import get_optional_user
from routers.api import jurisdictions as jurisdictions_router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(jurisdictions_router.get_router(), prefix="/jurisdictions")
    return TestClient(app)


def _default():
    return Identity(
        type="session", provider="github", provider_user_id="u2",
        email="d@x.com", role=Role.DEFAULT, user_id="user-456",
    )


def _contributor():
    return Identity(
        type="session", provider="github", provider_user_id="u1",
        email="u@x.com", role=Role.CONTRIBUTORS, user_id="user-123",
    )


def _maintainer():
    return Identity(
        type="session", provider="github", provider_user_id="u3",
        email="m@x.com", role=Role.MAINTAINERS, user_id="user-789",
    )


PATCH_BODY = {
    "jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:ca/place:oakland",
    "url": "https://oakland.gov",
}


@pytest.mark.unit
def test_patch_jurisdiction_data_opens_pr_for_maintainer(client):
    client.app.dependency_overrides[get_optional_user] = _maintainer
    with (
        patch(
            "services.jurisdiction_pull_request.open_jurisdiction_url_pr",
            new_callable=AsyncMock,
            return_value=(42, "https://github.com/x/pull/42"),
        ),
        patch(
            "services.jurisdiction_pull_request.merge_jurisdiction_pr",
            new_callable=AsyncMock,
        ) as mock_merge,
    ):
        response = client.patch("/jurisdictions/data", json=PATCH_BODY)

    assert response.status_code == 200
    assert response.json()["data"]["pull_request_number"] == 42
    # The opened PR is auto-merged via a background task.
    mock_merge.assert_awaited_once_with("42", "m@x.com")


@pytest.mark.unit
@pytest.mark.parametrize("identity", [_default, _contributor])
def test_patch_jurisdiction_data_requires_maintainer(client, identity):
    # The Jurisdiction Details sidebar edits published data via an auto-merged PR,
    # so it is gated to maintainers alongside the Current tab's people edits.
    client.app.dependency_overrides[get_optional_user] = identity
    with patch(
        "services.jurisdiction_pull_request.open_jurisdiction_url_pr",
        new_callable=AsyncMock,
    ) as mock_open:
        response = client.patch("/jurisdictions/data", json=PATCH_BODY)

    assert response.status_code == 403
    mock_open.assert_not_awaited()


@pytest.mark.unit
def test_get_jurisdiction_states_returns_list(client):
    mock_states = [{"code": "ca", "name": "California"}, {"code": "ny", "name": "New York"}]
    with patch(
        "shared.utils.config_utils.get_states",
        return_value=mock_states,
    ):
        response = client.get("/jurisdictions/states")

    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "total_items" in data
    assert data["total_items"] == 2


@pytest.mark.unit
def test_get_jurisdictions_by_ocdids_returns_data(client):
    with patch(
        "database.jurisdictions.get_jurisdictions_by_ocdids",
        new_callable=AsyncMock,
        return_value=[{"id": "ocd-jurisdiction/country:us/state:ca/place:oakland", "name": "Oakland"}],
    ):
        response = client.post(
            "/jurisdictions/by-ocdids",
            json={"ocdids": ["ocd-jurisdiction/country:us/state:ca/place:oakland"]},
        )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert isinstance(data["data"], list)


@pytest.mark.unit
def test_get_jurisdiction_history_returns_data(client):
    with patch(
        "database.jurisdictions.get_jurisdiction_history",
        new_callable=AsyncMock,
        return_value=[{"request_id": "req-1", "status": "complete"}],
    ):
        response = client.get(
            "/jurisdictions/history",
            params={"jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:ca/place:oakland"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data


@pytest.mark.unit
def test_get_jurisdiction_history_returns_404_when_none(client):
    with patch(
        "database.jurisdictions.get_jurisdiction_history",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = client.get(
            "/jurisdictions/history",
            params={"jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:ca/place:unknown"},
        )

    assert response.status_code == 404


@pytest.mark.unit
def test_get_jurisdiction_returns_data(client):
    with patch(
        "database.jurisdictions.get_jurisdiction",
        new_callable=AsyncMock,
        return_value={"data": {"id": "ocd-jurisdiction/country:us/state:ca/place:oakland", "name": "Oakland"}, "geo_center": None},
    ):
        response = client.get(
            "/jurisdictions",
            params={"jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:ca/place:oakland"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data


@pytest.mark.unit
def test_get_jurisdiction_returns_404_when_not_found(client):
    with patch(
        "database.jurisdictions.get_jurisdiction",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = client.get(
            "/jurisdictions",
            params={"jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:ca/place:unknown"},
        )

    assert response.status_code == 404
