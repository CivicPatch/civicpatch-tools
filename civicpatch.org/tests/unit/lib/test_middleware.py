"""Tests for the display_name-guard middleware.

The middleware redirects authenticated users with a NULL display_name to
`/settings`, while allowing anonymous users, allowlisted paths, and users
who have already picked a display_name to pass through.
"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient

from lib.middleware import require_display_name


def _app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(require_display_name)

    @app.get("/issues")
    async def issues():
        return PlainTextResponse("issues")

    @app.get("/settings")
    async def settings():
        return PlainTextResponse("settings")

    @app.get("/api/internal/user/display-name/suggestion")
    async def suggest():
        return {"data": "apple-witch"}

    @app.get("/api/permissions")
    async def permissions():
        return {"data": "ok"}

    @app.get("/frontend/build/foo.js")
    async def static_asset():
        return PlainTextResponse("// JS")

    return app


def _patch_session_returning(display_name):
    """Patch the middleware's session + user lookups to return a fake user."""
    session = {"provider": "supabase", "provider_user_id": "sb-1"}
    user_row = {"id": "uuid-1", "display_name": display_name}
    return patch.multiple(
        "lib.middleware",
        session_service=AsyncMock(get_session=AsyncMock(return_value=session)),
        user_database=AsyncMock(get_user=AsyncMock(return_value=user_row)),
    )


def _patch_no_session():
    """Patch session lookup to return None (cookie present but session expired)."""
    return patch(
        "lib.middleware.session_service.get_session",
        new_callable=AsyncMock,
        return_value=None,
    )


@pytest.mark.unit
def test_anonymous_request_passes_through():
    # No cookie → middleware doesn't even look at session, no redirect.
    client = TestClient(_app(), follow_redirects=False)
    response = client.get("/issues")

    assert response.status_code == 200
    assert response.text == "issues"


@pytest.mark.unit
def test_logged_in_without_display_name_redirected_to_settings():
    with _patch_session_returning(display_name=None):
        client = TestClient(_app(), follow_redirects=False)
        client.cookies.set("token", "fake-token")
        response = client.get("/issues")

    assert response.status_code == 303
    assert response.headers["location"] == "/settings"


@pytest.mark.unit
def test_logged_in_without_display_name_can_reach_settings():
    # Critical: prevents infinite redirect loop.
    with _patch_session_returning(display_name=None):
        client = TestClient(_app(), follow_redirects=False)
        client.cookies.set("token", "fake-token")
        response = client.get("/settings")

    assert response.status_code == 200
    assert response.text == "settings"


@pytest.mark.unit
def test_logged_in_without_display_name_can_reach_suggest_endpoint():
    # The /settings page calls the suggest endpoint to autofill — must not redirect.
    with _patch_session_returning(display_name=None):
        client = TestClient(_app(), follow_redirects=False)
        client.cookies.set("token", "fake-token")
        response = client.get("/api/internal/user/display-name/suggestion")

    assert response.status_code == 200


@pytest.mark.unit
def test_logged_in_without_display_name_can_load_frontend_assets():
    # Static assets must not be redirected — otherwise the /settings page is
    # served but its bundle returns 303 instead of JS, breaking the page.
    with _patch_session_returning(display_name=None):
        client = TestClient(_app(), follow_redirects=False)
        client.cookies.set("token", "fake-token")
        response = client.get("/frontend/build/foo.js")

    assert response.status_code == 200


@pytest.mark.unit
def test_logged_in_with_display_name_passes_through_all_routes():
    # Once user has picked a name, the gate releases.
    with _patch_session_returning(display_name="apple-witch"):
        client = TestClient(_app(), follow_redirects=False)
        client.cookies.set("token", "fake-token")
        response = client.get("/issues")

    assert response.status_code == 200


@pytest.mark.unit
def test_invalid_session_cookie_treated_as_anonymous():
    # If the cookie is stale (session expired in store), don't redirect — let
    # downstream auth handle it (likely a 401 from the actual route's Depends).
    with _patch_no_session():
        client = TestClient(_app(), follow_redirects=False)
        client.cookies.set("token", "stale-token")
        response = client.get("/issues")

    assert response.status_code == 200
