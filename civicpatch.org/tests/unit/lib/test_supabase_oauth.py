"""Supabase's auth API at the HTTP boundary: each test answers the requests the module sends."""

import json
from unittest.mock import patch

import httpx
import pytest

import lib.supabase_oauth as supabase_oauth
from lib.supabase_oauth import SupabaseAuthError

_URL = "http://sb"
_KEY = "secret"


def _supabase(handler):
    """Every httpx client the module opens talks to `handler` instead of the network."""
    real_client = httpx.AsyncClient
    return patch.object(
        supabase_oauth.httpx, "AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs)
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_closing_a_session_ends_only_that_session():
    sent = []
    with _supabase(lambda request: sent.append(request) or httpx.Response(204)):
        await supabase_oauth.close_session(_URL, _KEY, "user-token")

    assert sent[0].url.path == "/auth/v1/logout"
    assert sent[0].url.params["scope"] == "local"
    assert sent[0].headers["authorization"] == "Bearer user-token"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_a_session_is_minted_for_the_user_and_sends_no_email():
    def answer(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/v1/admin/users/sb-user-1":
            return httpx.Response(200, json={"email": "user@example.com"})
        if request.url.path == "/auth/v1/admin/generate_link":
            assert json.loads(request.content) == {"type": "magiclink", "email": "user@example.com"}
            return httpx.Response(200, json={"hashed_token": "hash-1"})
        assert request.url.path == "/auth/v1/verify"
        assert json.loads(request.content) == {"type": "magiclink", "token_hash": "hash-1"}
        return httpx.Response(200, json={"access_token": "user-token"})

    with _supabase(answer):
        assert await supabase_oauth.open_session(_URL, _KEY, "sb-user-1") == "user-token"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_admin_calls_carry_the_secret_key_and_user_calls_the_users_token():
    sent = []
    with _supabase(lambda request: sent.append(request) or httpx.Response(200, json=[])):
        await supabase_oauth.list_grants(_URL, _KEY, "user-token")
        await supabase_oauth._call("GET", f"{_URL}/auth/v1/admin/users/x", _KEY, None, None)

    assert sent[0].headers["authorization"] == "Bearer user-token"
    assert sent[1].headers["authorization"] == f"Bearer {_KEY}"
    assert all(request.headers["apikey"] == _KEY for request in sent)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_the_session_closes_even_when_the_block_fails():
    paths = []

    def answer(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("/verify"):
            return httpx.Response(200, json={"access_token": "user-token"})
        return httpx.Response(200, json={"email": "user@example.com", "hashed_token": "hash-1"})

    with _supabase(answer), pytest.raises(RuntimeError):
        async with supabase_oauth.user_session(_URL, _KEY, "sb-user-1"):
            raise RuntimeError("the call made with the session failed")

    assert paths[-1] == "/auth/v1/logout"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_revoking_names_the_app():
    sent = []
    with _supabase(lambda request: sent.append(request) or httpx.Response(204)):
        await supabase_oauth.revoke_grant(_URL, _KEY, "user-token", "client-1")

    assert (sent[0].method, sent[0].url.path, sent[0].url.params["client_id"]) == ("DELETE", "/auth/v1/user/oauth/grants", "client-1")


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.parametrize("field", ["redirect_url", "redirect_to"])
async def test_a_decision_answers_where_to_send_the_browser(field: str):
    with _supabase(lambda request: httpx.Response(200, json={field: "https://chatgpt.com/cb?code=1"})):
        redirect = await supabase_oauth.decide_authorization(_URL, _KEY, "abc123", "user-token", "approve")

    assert redirect == "https://chatgpt.com/cb?code=1"


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.parametrize(
    "response,message",
    [
        (httpx.Response(400, json={"msg": "authorization request cannot be processed"}), "authorization request cannot be processed"),
        (httpx.Response(404, text="404 page not found"), "404 page not found"),
    ],
)
async def test_a_refusal_keeps_supabases_message_and_status(response: httpx.Response, message: str):
    with _supabase(lambda request: response), pytest.raises(SupabaseAuthError) as raised:
        await supabase_oauth.list_grants(_URL, _KEY, "user-token")

    assert (str(raised.value), raised.value.status) == (message, response.status_code)
