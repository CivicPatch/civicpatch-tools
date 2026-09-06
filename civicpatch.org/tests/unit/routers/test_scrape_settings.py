"""Route contract for cadence and budget.

Thin: the SQL is integration-tested against real Postgres. What is worth pinning here is the
**split gate** — admins allocate, maintainers spend — because it is the one thing a reviewer
cannot see from either the schema or the query.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lib.auth import get_optional_user
from routers.api import scrape_settings as settings_router
from schemas.common import Identity, UserRole
from schemas.scrape_settings import GlobalScrapePanel, StateScrapePanel
from schemas.state_settings import GlobalSettings, StateSettings

pytestmark = pytest.mark.unit


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(settings_router.get_router(), prefix="/scrape_settings")
    return TestClient(app)


def _as(client, role):
    client.app.dependency_overrides[get_optional_user] = lambda: Identity(
        type="session",
        provider="github",
        provider_user_id="u1",
        email="u@x.com",
        role=role,
        user_id="user-1",
    )


def _patched():
    return (
        patch.object(settings_router.db, "set_cadence", new=AsyncMock()),
        patch.object(settings_router.db, "set_caps", new=AsyncMock()),
        patch.object(settings_router.db, "set_global_cap", new=AsyncMock()),
        patch.object(
            settings_router,
            "get_global_panel",
            new=AsyncMock(
                return_value=GlobalScrapePanel(
                    spent_this_month_usd=Decimal("9"), state_monthly_caps_usd=Decimal("50")
                )
            ),
        ),
        patch.object(
            settings_router.db,
            "get_state_settings",
            new=AsyncMock(return_value=StateSettings(state="wa")),
        ),
        patch.object(
            settings_router.db,
            "get_global_settings",
            new=AsyncMock(return_value=GlobalSettings()),
        ),
    )


def test_an_admin_may_set_the_cadence(client):
    _as(client, UserRole.ADMINS)
    with _patched()[0], _patched()[4]:
        response = client.put("/scrape_settings/wa/cadence", json={"cadence_days": 30})
    assert response.status_code == 200


@pytest.mark.parametrize("role", [UserRole.DEFAULT, UserRole.CONTRIBUTORS, UserRole.MAINTAINERS])
def test_nobody_below_admin_may_touch_cadence_or_caps(client, role):
    """Cadence and budget are one decision — how often a state is scraped is what it costs — so
    a maintainer able to set the schedule could set the spending without seeing the ceiling it
    is measured against."""
    _as(client, role)
    assert client.get("/scrape_settings/wa").status_code == 403
    assert client.get("/scrape_settings/global").status_code == 403
    assert client.put("/scrape_settings/wa/cadence", json={"cadence_days": 30}).status_code == 403
    assert client.put("/scrape_settings/wa/caps", json={"monthly_cap_usd": "1"}).status_code == 403
    assert client.put("/scrape_settings/global", json={"monthly_cap_usd": "1"}).status_code == 403


def test_an_admin_may_set_the_caps(client):
    _as(client, UserRole.ADMINS)
    with _patched()[1], _patched()[4]:
        response = client.put(
            "/scrape_settings/wa/caps", json={"monthly_cap_usd": "12.00"}
        )
    assert response.status_code == 200


def test_a_cadence_of_zero_days_is_refused_before_it_reaches_sql(client):
    """The CHECK constraint would catch it, but a 422 names the field and a CheckViolation
    does not."""
    _as(client, UserRole.ADMINS)
    response = client.put("/scrape_settings/wa/cadence", json={"cadence_days": 0})
    assert response.status_code == 422


def test_a_negative_cap_is_refused_before_it_reaches_sql(client):
    _as(client, UserRole.ADMINS)
    response = client.put("/scrape_settings/wa/caps", json={"monthly_cap_usd": "-1"})
    assert response.status_code == 422


def test_the_panel_is_one_response_rather_than_five(client):
    """The block renders as a unit. Five requests would let it paint in pieces, each from a
    slightly different moment — spend from one instant against a cap read at another."""
    _as(client, UserRole.ADMINS)
    panel = StateScrapePanel(
        state="wa",
        cadence_days=30,
        spent_this_month_usd=Decimal("1.50"),
        global_spent_this_month_usd=Decimal("9.00"),
        cost_cap_hits_this_month=2,
        candidates_due=41,
    )
    with patch.object(
        settings_router, "get_state_panel", new=AsyncMock(return_value=panel)
    ):
        body = client.get("/scrape_settings/wa").json()["data"]

    assert body["candidates_due"] == 41
    assert body["cost_cap_hits_this_month"] == 2


def test_the_state_caps_total_is_shown_even_when_it_exceeds_the_cap(client):
    """State caps adding up past the global one is normal: they are ceilings, not reservations."""
    _as(client, UserRole.ADMINS)
    with patch.object(
        settings_router,
        "get_global_panel",
        new=AsyncMock(
            return_value=GlobalScrapePanel(
                monthly_cap_usd=Decimal("40"),
                spent_this_month_usd=Decimal("9"),
                state_monthly_caps_usd=Decimal("120"),
            )
        ),
    ):
        body = client.get("/scrape_settings/global").json()["data"]

    assert body["state_monthly_caps_usd"] == "120"
