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


@pytest.mark.parametrize("role", [UserRole.MAINTAINERS, UserRole.ADMINS])
def test_a_maintainer_may_set_how_often_a_state_is_scraped(client, role):
    _as(client, role)
    with _patched()[0], _patched()[3]:
        response = client.put("/scrape_settings/wa/cadence", json={"cadence_days": 30})
    assert response.status_code == 200


def test_a_maintainer_may_not_set_what_a_state_may_spend(client):
    """The split the plan settled: admins allocate, maintainers spend. A maintainer raising
    their own state's cap would make the fleet budget advisory."""
    _as(client, UserRole.MAINTAINERS)
    response = client.put(
        "/scrape_settings/wa/caps", json={"monthly_cap_usd": "999"}
    )
    assert response.status_code == 403


def test_an_admin_may_set_the_caps(client):
    _as(client, UserRole.ADMINS)
    with _patched()[1], _patched()[3]:
        response = client.put(
            "/scrape_settings/wa/caps", json={"monthly_cap_usd": "12.00"}
        )
    assert response.status_code == 200


def test_a_maintainer_may_not_set_the_global_cap(client):
    _as(client, UserRole.MAINTAINERS)
    response = client.put("/scrape_settings/global", json={"monthly_cap_usd": "40"})
    assert response.status_code == 403


def test_a_contributor_may_not_even_read_the_settings(client):
    """Read is Maintainer-and-up, matching the spend figures these are read against."""
    _as(client, UserRole.CONTRIBUTORS)
    assert client.get("/scrape_settings/wa").status_code == 403
    assert client.get("/scrape_settings/global").status_code == 403


def test_a_cadence_of_zero_days_is_refused_before_it_reaches_sql(client):
    """The CHECK constraint would catch it, but a 422 names the field and a CheckViolation
    does not."""
    _as(client, UserRole.MAINTAINERS)
    response = client.put("/scrape_settings/wa/cadence", json={"cadence_days": 0})
    assert response.status_code == 422


def test_a_negative_cap_is_refused_before_it_reaches_sql(client):
    _as(client, UserRole.ADMINS)
    response = client.put(
        "/scrape_settings/wa/caps", json={"monthly_cap_usd": "-1"}
    )
    assert response.status_code == 422
