import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.templating import Jinja2Templates
from unittest.mock import AsyncMock, patch

from routers.frontend import build_permissions, get_router
from schemas.common import Identity, Role
from lib.auth import get_optional_user


def _identity(*roles: Role) -> Identity:
    return Identity(
        type="session",
        provider="github",
        provider_user_id="123",
        email="user@example.com",
        teams=list(roles),
    )


UNAUTHENTICATED = None
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


@pytest.mark.unit
def test_permissions_logged_in_no_teams():
    """GitHub user who authenticated but is not a member of any CivicPatch team."""
    p = build_permissions(_identity())
    assert p["can_view_queue_page"] is False
    assert p["can_view_queue_page_errors"] is False
    assert p["can_view_jurisdiction_page"] is False
    assert p["can_view_reviews_page"] is False
    assert p["can_view_issues_page"] is False
    assert p["can_delete_directory_person"] is False


@pytest.mark.unit
def test_permissions_default_role():
    p = build_permissions(DEFAULT)
    assert p["can_view_queue_page"] is True
    assert p["can_view_queue_page_errors"] is False
    assert p["can_view_jurisdiction_page"] is True
    assert p["can_scrape_local"] is False
    assert p["can_scrape_remote"] is False
    assert p["can_view_reviews_page"] is True
    assert p["can_view_issues_page"] is False
    assert p["can_delete_directory_person"] is False


@pytest.mark.unit
def test_permissions_contributor_role():
    p = build_permissions(CONTRIBUTOR)
    assert p["can_view_queue_page"] is True
    assert p["can_view_queue_page_errors"] is False
    assert p["can_view_jurisdiction_page"] is True
    assert p["can_scrape_remote"] is False
    assert p["can_view_reviews_page"] is True
    assert p["can_view_issues_page"] is False
    assert p["can_delete_directory_person"] is True


@pytest.mark.unit
def test_permissions_maintainer_role():
    p = build_permissions(MAINTAINER)
    assert p["can_view_queue_page"] is True
    assert p["can_view_queue_page_errors"] is False
    assert p["can_view_jurisdiction_page"] is True
    assert p["can_scrape_remote"] is True
    assert p["can_view_reviews_page"] is True
    assert p["can_view_issues_page"] is True
    assert p["can_delete_directory_person"] is False


@pytest.mark.unit
def test_permissions_admin_role():
    p = build_permissions(ADMIN)
    assert p["can_view_queue_page"] is True
    assert p["can_view_queue_page_errors"] is True
    assert p["can_scrape_remote"] is False
    assert p["can_view_issues_page"] is False
    assert p["can_delete_directory_person"] is False



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
    """can_scrape_local is True for maintainers outside production."""
    import routers.frontend as frontend_module
    original = frontend_module._is_production
    try:
        frontend_module._is_production = False
        assert build_permissions(MAINTAINER)["can_scrape_local"] is True
        assert build_permissions(DEFAULT)["can_scrape_local"] is False
        assert build_permissions(CONTRIBUTOR)["can_scrape_local"] is False
        assert build_permissions(None)["can_scrape_local"] is False
    finally:
        frontend_module._is_production = original


# ── GET /api/permissions ──────────────────────────────────────────────────────

@pytest.fixture
def permissions_client():
    app = FastAPI()
    templates = Jinja2Templates(directory="src/frontend/templates")
    app.include_router(get_router(templates))
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
    assert data["data"]["permissions"]["can_view_issues_page"] is True
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
    assert data["data"]["permissions"]["can_scrape_remote"] is False
