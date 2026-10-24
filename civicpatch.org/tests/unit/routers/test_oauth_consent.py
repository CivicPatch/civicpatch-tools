from contextlib import ExitStack, contextmanager
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient

from frontend.vite import vite_asset, vite_css
from lib.auth import get_optional_user
from lib.auth_session import CSRF_COOKIE
from lib.supabase_oauth import APPROVE, SupabaseAuthError
from routers import oauth_consent
from schemas.common import Identity, UserRole

_AUTHORIZATION_ID = "abc123"
_SUPABASE_USER_ID = "sb-user-1"
_CALLBACK = "https://chatgpt.com/callback?code=xyz"


def _identity(role: UserRole) -> Identity:
    return Identity(
        type="cookie", provider="supabase", provider_user_id=_SUPABASE_USER_ID,
        email="user@example.com", role=role.value, user_id="u-1", username="someone",
    )


def _client(identity: Identity | None) -> TestClient:
    app = FastAPI()
    templates = Jinja2Templates(directory="src/frontend/templates")
    templates.env.globals["vite_asset"] = lambda path: vite_asset(path, False)
    templates.env.globals["vite_css"] = lambda path: vite_css(path, False)
    app.include_router(oauth_consent.get_router(templates))
    app.mount("/frontend", StaticFiles(directory="src/frontend"), name="frontend")
    app.dependency_overrides[get_optional_user] = lambda: identity
    return TestClient(app, follow_redirects=False)


@contextmanager
def _service(**overrides):
    calls = {
        "fetch_authorization_request": AsyncMock(return_value={"client": {"name": "ChatGPT"}}),
        "decide_authorization_request": AsyncMock(return_value=_CALLBACK),
        **overrides,
    }
    with ExitStack() as stack:
        for name, mock in calls.items():
            stack.enter_context(patch.object(oauth_consent.service, name, mock))
        stack.enter_context(
            patch.object(oauth_consent.environment, "supabase_url_and_secret_key", return_value=("http://sb", "secret"))
        )
        yield calls


def _consent_url(authorization_id: str = _AUTHORIZATION_ID) -> str:
    return f"{oauth_consent.CONSENT_PATH}?authorization_id={authorization_id}"


def _approve(client: TestClient):
    return client.post(oauth_consent.CONSENT_PATH, data={"authorization_id": _AUTHORIZATION_ID, "action": APPROVE})


@pytest.mark.unit
def test_a_signed_out_visitor_signs_in_and_comes_back():
    response = _client(None).get(_consent_url())

    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=%2Foauth%2Fconsent%3Fauthorization_id%3Dabc123"


@pytest.mark.unit
def test_a_contributor_is_told_only_maintainers_connect_apps():
    with _service() as calls:
        response = _client(_identity(UserRole.CONTRIBUTORS)).get(_consent_url())

    assert oauth_consent.NOT_A_MAINTAINER in response.text
    calls["fetch_authorization_request"].assert_not_awaited()


@pytest.mark.unit
def test_a_maintainer_sees_who_is_asking_with_the_csrf_token_in_the_form():
    client = _client(_identity(UserRole.MAINTAINERS))
    client.cookies.set(CSRF_COOKIE, "nonce-1")
    with _service() as calls:
        response = client.get(_consent_url())

    assert response.status_code == 200
    assert "<strong>ChatGPT</strong>" in response.text
    assert 'name="csrf_token" value="nonce-1"' in response.text
    calls["fetch_authorization_request"].assert_awaited_once_with("http://sb", "secret", _SUPABASE_USER_ID, _AUTHORIZATION_ID)


@pytest.mark.unit
@pytest.mark.parametrize("field", ["redirect_url", "redirect_to"])
def test_an_app_already_approved_goes_straight_back_with_no_question(field: str):
    with _service(fetch_authorization_request=AsyncMock(return_value={field: _CALLBACK})):
        response = _client(_identity(UserRole.MAINTAINERS)).get(_consent_url())

    assert response.status_code == 303
    assert response.headers["location"] == _CALLBACK


@pytest.mark.unit
def test_an_unusable_request_says_so():
    with _service(fetch_authorization_request=AsyncMock(side_effect=SupabaseAuthError("not found", 404))):
        response = _client(_identity(UserRole.MAINTAINERS)).get(_consent_url())

    assert oauth_consent.REQUEST_UNUSABLE in response.text


@pytest.mark.unit
def test_a_malformed_authorization_id_is_refused_before_supabase():
    with _service() as calls:
        response = _client(_identity(UserRole.MAINTAINERS)).get(_consent_url("not/an id"))

    assert response.status_code == 422
    calls["fetch_authorization_request"].assert_not_awaited()


@pytest.mark.unit
def test_approving_sends_the_browser_back_to_the_app():
    with _service() as calls:
        response = _approve(_client(_identity(UserRole.MAINTAINERS)))

    assert response.status_code == 303
    assert response.headers["location"] == _CALLBACK
    calls["decide_authorization_request"].assert_awaited_once_with(
        "http://sb", "secret", _SUPABASE_USER_ID, _AUTHORIZATION_ID, APPROVE
    )


@pytest.mark.unit
def test_an_approval_supabase_refuses_says_so():
    with _service(decide_authorization_request=AsyncMock(side_effect=SupabaseAuthError("cannot be processed", 400))):
        response = _approve(_client(_identity(UserRole.MAINTAINERS)))

    assert oauth_consent.REQUEST_UNUSABLE in response.text


@pytest.mark.unit
def test_a_contributor_cannot_approve():
    with _service() as calls:
        response = _approve(_client(_identity(UserRole.CONTRIBUTORS)))

    assert response.status_code == 403
    calls["decide_authorization_request"].assert_not_awaited()
