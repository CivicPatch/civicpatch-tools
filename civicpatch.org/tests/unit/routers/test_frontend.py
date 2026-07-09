from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from fastapi.templating import Jinja2Templates

from routers.frontend import build_permissions, get_router
from schemas.common import Identity, Role
from lib.auth import get_optional_user


_LADDER_ORDER = [Role.DEFAULT, Role.CONTRIBUTORS, Role.MAINTAINERS, Role.ADMINS]


def _identity(*roles: Role) -> Identity:
    """Build an Identity at the highest level in `roles`.

    The vararg signature preserves call-site compatibility from the pre-ladder
    days — callers used to pass `(Role.CONTRIBUTORS, Role.DEFAULT)` for a flat
    set; now the highest of those collapses to a single role.
    """
    if roles:
        highest = max(roles, key=_LADDER_ORDER.index)
        role_value = highest.value
    else:
        role_value = Role.DEFAULT.value
    return Identity(
        type="session",
        provider="github",
        provider_user_id="123",
        email="user@example.com",
        role=role_value,
    )


DEFAULT = _identity(Role.DEFAULT)
CONTRIBUTOR = _identity(Role.CONTRIBUTORS, Role.DEFAULT)
MAINTAINER = _identity(Role.MAINTAINERS, Role.DEFAULT)
ADMIN = _identity(Role.ADMINS, Role.DEFAULT)


# ── build_permissions ─────────────────────────────────────────────────────────

@pytest.mark.unit
def test_permissions_unauthenticated():
    p = build_permissions(None)
    assert p["can_view_queue_page"] is False
    assert p["can_view_queue_page_errors"] is False
    assert p["can_view_jurisdiction_page"] is False
    assert p["can_scrape_local"] is False
    assert p["can_scrape_remote"] is False
    assert p["can_view_reviews_page"] is False
    assert p["can_view_issues_page"] is False
    assert p["can_delete_directory_person"] is False
    assert p["can_close_pull_request"] is False


@pytest.mark.unit
def test_permissions_default_role():
    p = build_permissions(DEFAULT)
    assert p["can_view_queue_page"] is False  # Contributors+ only
    assert p["can_view_queue_page_errors"] is False
    assert p["can_view_jurisdiction_page"] is True
    assert p["can_scrape_local"] is False
    assert p["can_scrape_remote"] is False
    assert p["can_view_reviews_page"] is True
    assert p["can_view_issues_page"] is False
    assert p["can_delete_directory_person"] is False
    assert p["can_close_pull_request"] is False  # contributor+ only


@pytest.mark.unit
def test_permissions_contributor_role():
    p = build_permissions(CONTRIBUTOR)
    assert p["can_view_queue_page"] is True  # introduced at Contributor
    assert p["can_view_queue_page_errors"] is False
    assert p["can_view_jurisdiction_page"] is True
    assert p["can_scrape_remote"] is False
    assert p["can_view_reviews_page"] is True
    assert p["can_view_issues_page"] is False
    assert p["can_delete_directory_person"] is True
    assert p["can_close_pull_request"] is True  # introduced at Contributor


@pytest.mark.unit
def test_permissions_maintainer_role():
    """Maintainer inherits Contributor's powers under the ladder.
    Issues page is now Admin-only — Maintainer does not see it."""
    p = build_permissions(MAINTAINER)
    assert p["can_view_queue_page"] is True
    assert p["can_view_queue_page_errors"] is False
    assert p["can_view_jurisdiction_page"] is True
    assert p["can_scrape_remote"] is True
    assert p["can_view_reviews_page"] is True
    assert p["can_view_issues_page"] is False  # Admin-only
    assert p["can_delete_directory_person"] is True
    assert p["can_close_pull_request"] is True


@pytest.mark.unit
def test_permissions_admin_role():
    """Admin inherits Maintainer + Contributor powers under the ladder, and
    gains the Issues page + queue-error visibility on top."""
    p = build_permissions(ADMIN)
    assert p["can_view_queue_page"] is True
    assert p["can_view_queue_page_errors"] is True
    assert p["can_scrape_remote"] is True
    assert p["can_view_issues_page"] is True
    assert p["can_delete_directory_person"] is True
    assert p["can_close_pull_request"] is True
    assert p["can_manage_roles"] is True


@pytest.mark.unit
def test_scrape_local_false_in_production():
    """can_scrape_local is always False in production regardless of role."""
    import routers.frontend as frontend_module
    original = frontend_module._is_production
    try:
        frontend_module._is_production = True
        for identity in [None, DEFAULT, CONTRIBUTOR, MAINTAINER, ADMIN]:
            assert build_permissions(identity)["can_scrape_local"] is False
    finally:
        frontend_module._is_production = original


@pytest.mark.unit
def test_scrape_local_true_for_maintainers_in_dev():
    """can_scrape_local is True for maintainers and admins outside production."""
    import routers.frontend as frontend_module
    original = frontend_module._is_production
    try:
        frontend_module._is_production = False
        assert build_permissions(MAINTAINER)["can_scrape_local"] is True
        assert build_permissions(ADMIN)["can_scrape_local"] is True
        assert build_permissions(CONTRIBUTOR)["can_scrape_local"] is False
        assert build_permissions(DEFAULT)["can_scrape_local"] is False
        assert build_permissions(None)["can_scrape_local"] is False
    finally:
        frontend_module._is_production = original


# ── GET /api/permissions ──────────────────────────────────────────────────────

@pytest.fixture
def permissions_client():
    app = FastAPI()
    templates = Jinja2Templates(directory="src/frontend/templates")
    app.include_router(get_router(templates))
    # layouts/base.html resolves CSS/JS via url_for('frontend', path=...) — mount matches
    # main.py's real one so any test rendering a full page template (extends base.html)
    # doesn't 500/NoMatchFound on assets it never actually requests in a unit test.
    app.mount("/frontend", StaticFiles(directory="src/frontend"), name="frontend")
    return app


@pytest.mark.unit
def test_permissions_endpoint_unauthenticated(permissions_client):
    permissions_client.dependency_overrides[get_optional_user] = lambda: None
    client = TestClient(permissions_client)
    response = client.get("/api/permissions")
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is False
    assert data["data"]["permissions"]["can_view_queue_page"] is False
    assert data["data"]["permissions"]["can_scrape_remote"] is False


@pytest.mark.unit
def test_permissions_endpoint_maintainer(permissions_client):
    permissions_client.dependency_overrides[get_optional_user] = lambda: MAINTAINER
    client = TestClient(permissions_client)
    response = client.get("/api/permissions")
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is True
    assert data["data"]["permissions"]["can_view_queue_page"] is True
    assert data["data"]["permissions"]["can_scrape_remote"] is True
    assert data["data"]["permissions"]["can_view_issues_page"] is False  # Admin-only
    assert data["data"]["permissions"]["can_view_queue_page_errors"] is False


@pytest.mark.unit
def test_permissions_endpoint_admin(permissions_client):
    permissions_client.dependency_overrides[get_optional_user] = lambda: ADMIN
    client = TestClient(permissions_client)
    response = client.get("/api/permissions")
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is True
    assert data["data"]["permissions"]["can_view_queue_page_errors"] is True
    # Under the ladder, admin >= maintainer, so scrape_remote is now True.
    assert data["data"]["permissions"]["can_scrape_remote"] is True


# ── GET /{state}/local ────────────────────────────────────────────────────────
# Must be registered ahead of the /{path:path} catch-all (jurisdiction_page), which
# requires >=3 path segments and would otherwise 404 on a bare "{state}/local".

@pytest.mark.unit
def test_municipalities_page_takes_priority_over_catch_all(permissions_client):
    permissions_client.dependency_overrides[get_optional_user] = lambda: None
    client = TestClient(permissions_client)
    response = client.get("/nc/local")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.unit
def test_catch_all_still_handles_three_segment_jurisdiction_paths(permissions_client):
    permissions_client.dependency_overrides[get_optional_user] = lambda: None
    client = TestClient(permissions_client)
    # Unrelated to the new route: a well-formed 3-segment path should still reach
    # jurisdiction_page (mocked here as "not found"), not the new /{state}/local route.
    with patch("routers.frontend.get_jurisdiction", new_callable=AsyncMock, return_value=None):
        response = client.get("/nc/local/place_does_not_exist")
    assert response.status_code == 404
