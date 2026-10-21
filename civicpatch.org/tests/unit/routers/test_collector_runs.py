import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

import services.collector_runs as collector_runs_service
from lib.auth import get_optional_user
from routers.api import collector_runs as collector_runs_router
from schemas.common import Identity, UserRole
from services.collector_runs import AlreadyCollecting, ClaimedRun, UnknownJurisdiction
from shared.utils.statuses import PipelineRunKind

pytestmark = pytest.mark.unit

OCDID = "ocd-jurisdiction/country:us/state:vt/place:stowe/government"
_CLAIMED = ClaimedRun(jurisdiction_ocdid=OCDID, pipeline_run_id="run-1", name="Stowe town")


def _admin():
    return Identity(type="session", provider="github", provider_user_id="u1", email="a@x.com", role=UserRole.ADMINS, user_id="user-1")


def _maintainer():
    return Identity(type="session", provider="github", provider_user_id="u2", email="m@x.com", role=UserRole.MAINTAINERS, user_id="user-2")


def _service_key():
    return Identity(type="service_api_key", provider="system", provider_user_id="service_api_key", email=None)


@pytest.fixture(params=[PipelineRunKind.GOVERNING_LAW_COLLECTOR, PipelineRunKind.ORGANIZATIONS_COLLECTOR])
def kind(request):
    return request.param


@pytest.fixture
def url(kind):
    return f"/pipeline_runs/{kind}"


@pytest.fixture
def client(kind, url):
    app = FastAPI()
    app.include_router(collector_runs_router.get_router(kind), prefix=url)
    return TestClient(app)


def _start(client, url, identity, raises=None):
    client.app.dependency_overrides[get_optional_user] = identity
    with patch.object(collector_runs_service, "start_collection", new=AsyncMock(return_value=_CLAIMED, side_effect=raises)) as start:
        response = client.post(url, json={"jurisdiction_ocdid": OCDID})
    return response, start


def test_an_admin_starts_one_jurisdictions_collection_of_the_mounted_kind(client, url, kind):
    response, start = _start(client, url, _admin)

    assert response.status_code == 200, response.text
    assert response.json()["data"]["pipeline_run_id"] == "run-1"
    assert start.await_args is not None
    assert start.await_args.args[:3] == (kind, OCDID, "user-1")


def test_an_unknown_jurisdiction_is_404_and_one_already_collecting_409(client, url):
    assert _start(client, url, _admin, raises=UnknownJurisdiction(OCDID))[0].status_code == 404
    assert _start(client, url, _admin, raises=AlreadyCollecting(OCDID))[0].status_code == 409


def test_a_maintainer_cannot_start_one(client, url):
    response, start = _start(client, url, _maintainer)

    assert response.status_code == 403
    start.assert_not_awaited()


def test_an_admin_starts_a_states_collection(client, url, kind):
    client.app.dependency_overrides[get_optional_user] = _admin
    with patch("routers.api.collector_runs.temporal_service.start_collector_state_workflow", new=AsyncMock(return_value="collector-state-vt")) as start:
        response = client.post(f"{url}/batch", json={"state": "vt"})

    assert response.status_code == 200, response.text
    assert response.json()["data"]["workflow_id"] == "collector-state-vt"
    assert start.await_args is not None
    assert start.await_args.args[:4] == (kind, "vt", None, "user-1")


def test_only_the_service_key_claims_and_asks_the_budget(client, url, kind):
    client.app.dependency_overrides[get_optional_user] = _service_key
    with patch.object(collector_runs_service, "claim_jurisdictions", new=AsyncMock(return_value=[_CLAIMED])) as claim, patch(
        "routers.api.collector_runs.spend_budget_service.cap_reached_for_collector", new=AsyncMock(return_value=None)
    ) as cap:
        assert client.post(f"{url}/claim", json={"state": "vt", "num_jurisdictions": 5}).json()["data"]["jurisdictions"][0]["pipeline_run_id"] == "run-1"
        assert client.get(f"{url}/budget_cap").json() == {"data": {"cap": None}}
    assert claim.await_args is not None
    assert claim.await_args.args[0] == kind
    cap.assert_awaited_once_with(kind)

    client.app.dependency_overrides[get_optional_user] = _admin
    assert client.post(f"{url}/claim", json={"state": "vt"}).status_code == 403


@pytest.mark.parametrize("method, path, body", [
    ("post", "", {"jurisdiction_ocdid": OCDID}),
    ("post", "/batch", {"state": "vt"}),
    ("post", "/claim", {"state": "vt"}),
    ("get", "/budget_cap", None),
])
def test_nobody_signed_out_reaches_any_route(client, url, method, path, body):
    client.app.dependency_overrides[get_optional_user] = lambda: None
    response = client.request(method, f"{url}{path}", json=body)

    assert response.status_code == 403
