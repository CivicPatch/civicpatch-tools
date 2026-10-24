from contextlib import ExitStack, contextmanager
from unittest.mock import AsyncMock, patch

import pytest

import lib.supabase_oauth as supabase_oauth
import services.connected_apps as service
from lib.supabase_oauth import SupabaseAuthError
from schemas.connected_apps import ConnectedApp

_GRANT = {
    "client": {"id": "1e2c2d5d-e8c9-4a46-b6d4-6eab46d2653e", "name": "ChatGPT"},
    "scopes": ["openid", "email"],
    "granted_at": "2026-10-24T03:01:04.350622Z",
}


@contextmanager
def _supabase(**overrides):
    """The session is opened and closed in lib.supabase_oauth; the calls made with it, here."""
    sessions = {"open_session": AsyncMock(return_value="one-off-token"), "close_session": AsyncMock()}
    calls = {
        "list_grants": AsyncMock(return_value=[_GRANT]),
        "revoke_grant": AsyncMock(),
        "fetch_authorization": AsyncMock(return_value={"client": {"name": "ChatGPT"}}),
        "decide_authorization": AsyncMock(return_value="https://chatgpt.com/callback?code=xyz"),
        **overrides,
    }
    with ExitStack() as stack:
        for name, mock in sessions.items():
            stack.enter_context(patch.object(supabase_oauth, name, mock))
        for name, mock in calls.items():
            stack.enter_context(patch.object(service, name, mock))
        yield {**sessions, **calls}


@pytest.mark.asyncio
@pytest.mark.unit
async def test_the_users_approved_apps_come_back_as_connected_apps():
    with _supabase() as calls:
        apps = await service.fetch_connected_apps("http://sb", "secret", "sb-user-1")

    assert apps == [ConnectedApp(client_id=_GRANT["client"]["id"], name="ChatGPT", granted_at=_GRANT["granted_at"])]
    calls["open_session"].assert_awaited_once_with("http://sb", "secret", "sb-user-1")
    calls["close_session"].assert_awaited_once_with("http://sb", "secret", "one-off-token")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_no_oauth_server_means_no_apps():
    with _supabase(list_grants=AsyncMock(side_effect=SupabaseAuthError("404 page not found", 404))) as calls:
        assert await service.fetch_connected_apps("http://sb", "secret", "sb-user-1") == []

    calls["close_session"].assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_any_other_supabase_error_is_raised_after_closing_the_session():
    with _supabase(list_grants=AsyncMock(side_effect=SupabaseAuthError("boom", 500))) as calls:
        with pytest.raises(SupabaseAuthError):
            await service.fetch_connected_apps("http://sb", "secret", "sb-user-1")

    calls["close_session"].assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_disconnecting_revokes_that_app_for_the_user():
    with _supabase() as calls:
        await service.disconnect_app("http://sb", "secret", "sb-user-1", _GRANT["client"]["id"])

    calls["revoke_grant"].assert_awaited_once_with("http://sb", "secret", "one-off-token", _GRANT["client"]["id"])
    calls["close_session"].assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_a_request_is_read_with_the_users_session():
    with _supabase() as calls:
        authorization = await service.fetch_authorization_request("http://sb", "secret", "sb-user-1", "abc123")

    assert authorization == {"client": {"name": "ChatGPT"}}
    calls["fetch_authorization"].assert_awaited_once_with("http://sb", "secret", "abc123", "one-off-token")
    calls["close_session"].assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_a_refused_decision_still_closes_the_session():
    with _supabase(decide_authorization=AsyncMock(side_effect=SupabaseAuthError("cannot be processed", 400))) as calls:
        with pytest.raises(SupabaseAuthError):
            await service.decide_authorization_request("http://sb", "secret", "sb-user-1", "abc123", "approve")

    calls["close_session"].assert_awaited_once_with("http://sb", "secret", "one-off-token")
