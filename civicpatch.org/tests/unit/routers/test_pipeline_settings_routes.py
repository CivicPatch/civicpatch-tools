"""Route contract for every pipeline's cadence and caps per state. Thin: the SQL is integration-tested.
What is pinned here is the admin gate, the validation, and that each route names its pipeline."""

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lib.auth import get_optional_user
from routers.api import pipeline_settings as settings_router
from schemas.common import Identity, UserRole
from schemas.pipeline_settings import GlobalPanel, PipelinePanel
from shared.utils.statuses import PipelineRunKind

pytestmark = pytest.mark.unit

_LAW = PipelineRunKind.GOVERNING_LAW_COLLECTOR


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(settings_router.get_router(), prefix="/pipeline_settings")
    return TestClient(app)


def _as(client, role):
    client.app.dependency_overrides[get_optional_user] = lambda: Identity(
        type="session", provider="github", provider_user_id="u1", email="u@x.com", role=role, user_id="user-1"
    )


def _panel(kind: PipelineRunKind = _LAW) -> PipelinePanel:
    return PipelinePanel(
        state="wa",
        kind=kind,
        spent_this_month_usd=Decimal("1.50"),
        global_spent_this_month_usd=Decimal("9.00"),
        cost_cap_hits_this_month=2,
        candidates_due=41,
    )


def test_an_admin_sets_a_pipelines_cadence_and_its_schedule_follows(client):
    _as(client, UserRole.ADMINS)
    with patch.object(settings_router.db, "set_cadence", new=AsyncMock()) as set_cadence, patch.object(
        settings_router, "reconcile_state_schedule", new=AsyncMock()
    ) as reconcile, patch.object(settings_router, "get_client", new=AsyncMock()), patch.object(
        settings_router, "get_pipeline_panel", new=AsyncMock(return_value=_panel())
    ):
        response = client.put("/pipeline_settings/wa/governing_law_collector/cadence", json={"cadence_days": 365})

    assert response.status_code == 200, response.text
    assert set_cadence.await_args.args[:3] == ("wa", _LAW, 365)
    assert reconcile.await_args.args[1:] == ("wa", _LAW)


def test_an_admin_sets_a_pipelines_caps(client):
    _as(client, UserRole.ADMINS)
    with patch.object(settings_router.db, "set_caps", new=AsyncMock()) as set_caps, patch.object(
        settings_router, "get_pipeline_panel", new=AsyncMock(return_value=_panel())
    ):
        response = client.put(
            "/pipeline_settings/wa/governing_law_collector/caps", json={"pipeline_run_cap_usd": "0.25", "monthly_cap_usd": "20"}
        )

    assert response.status_code == 200, response.text
    set_caps.assert_awaited_once_with("wa", _LAW, Decimal("0.25"), Decimal("20"), "user-1")


@pytest.mark.parametrize("role", [UserRole.DEFAULT, UserRole.CONTRIBUTORS, UserRole.MAINTAINERS])
def test_nobody_below_admin_may_read_or_set_settings(client, role):
    """How often a pipeline runs is what it costs, so one role sets both."""
    _as(client, role)
    assert client.get("/pipeline_settings/wa/people_collector").status_code == 403
    assert client.get("/pipeline_settings/global").status_code == 403
    assert client.put("/pipeline_settings/wa/people_collector/cadence", json={"cadence_days": 30}).status_code == 403
    assert client.put("/pipeline_settings/wa/people_collector/caps", json={"monthly_cap_usd": "1"}).status_code == 403
    assert client.put("/pipeline_settings/global", json={"monthly_cap_usd": "1"}).status_code == 403


def test_a_cadence_of_zero_days_is_refused_before_it_reaches_sql(client):
    _as(client, UserRole.ADMINS)
    assert client.put("/pipeline_settings/wa/people_collector/cadence", json={"cadence_days": 0}).status_code == 422


def test_a_negative_cap_is_refused_before_it_reaches_sql(client):
    _as(client, UserRole.ADMINS)
    assert client.put("/pipeline_settings/wa/people_collector/caps", json={"monthly_cap_usd": "-1"}).status_code == 422


def test_an_unknown_pipeline_is_refused(client):
    _as(client, UserRole.ADMINS)
    assert client.get("/pipeline_settings/wa/not_a_pipeline").status_code == 422


def test_the_panel_is_one_response_for_one_pipeline_in_one_state(client):
    _as(client, UserRole.ADMINS)
    with patch.object(settings_router, "get_pipeline_panel", new=AsyncMock(return_value=_panel())) as panel:
        body = client.get("/pipeline_settings/wa/governing_law_collector").json()["data"]

    panel.assert_awaited_once_with("wa", _LAW)
    assert body["kind"] == "governing_law_collector"
    assert body["candidates_due"] == 41


def test_the_caps_total_is_shown_even_when_it_exceeds_the_global_cap(client):
    """The caps adding up past the global one is normal: they are ceilings, not reservations."""
    _as(client, UserRole.ADMINS)
    panel = GlobalPanel(
        monthly_cap_usd=Decimal("40"),
        spent_this_month_usd=Decimal("9"),
        monthly_caps_usd=Decimal("120"),
        pipeline_run_concurrency=25,
    )
    with patch.object(settings_router, "get_global_panel", new=AsyncMock(return_value=panel)):
        body = client.get("/pipeline_settings/global").json()["data"]

    assert body["monthly_caps_usd"] == "120"
