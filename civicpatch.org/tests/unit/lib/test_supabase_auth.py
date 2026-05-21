from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.supabase_auth import SupabaseUser, create_supabase_client, verify_jwt


# Justification per CLAUDE.md test-change rule:
# - The "raises when env missing" test from Phase A is removed. SUPABASE_URL and
#   SUPABASE_SECRET_KEY are now REQUIRED env vars validated at app boot by
#   environment.get_env_vars(); the runtime guard inside the client constructor
#   is no longer reachable.
# - The "builds client" test now exercises create_supabase_client() (async,
#   called once from FastAPI lifespan) and patches acreate_client. The previous
#   sync get_supabase_client + create_client surface was replaced by the async
#   AsyncClient API so verify_jwt no longer needs asyncio.to_thread.
# - The verify_jwt tests now mock client.auth.get_user as AsyncMock (was
#   MagicMock) because the call is awaited directly instead of being wrapped
#   in asyncio.to_thread.


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_supabase_client_builds_client_when_configured():
    with (
        patch(
            "lib.supabase_auth.environment.get_env_vars",
            return_value={
                "SUPABASE_URL": "https://example.supabase.co",
                "SUPABASE_SECRET_KEY": "sb_secret_test",
            },
        ),
        patch(
            "lib.supabase_auth.acreate_client",
            new_callable=AsyncMock,
        ) as mock_acreate,
    ):
        mock_acreate.return_value = MagicMock()
        client = await create_supabase_client()

    mock_acreate.assert_awaited_once_with(
        "https://example.supabase.co", "sb_secret_test"
    )
    assert client is mock_acreate.return_value


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_jwt_returns_supabase_user_on_success():
    mock_user = MagicMock()
    mock_user.id = "user-uuid"
    mock_user.email = "alice@example.com"
    mock_user.user_metadata = {"full_name": "Alice"}

    mock_client = MagicMock()
    mock_client.auth.get_user = AsyncMock(return_value=MagicMock(user=mock_user))

    result = await verify_jwt(mock_client, "fake.jwt.token")

    assert result == SupabaseUser(
        id="user-uuid", email="alice@example.com", display_name="Alice"
    )
    assert result.provider == "supabase"
    mock_client.auth.get_user.assert_awaited_once_with("fake.jwt.token")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_jwt_raises_when_user_is_none():
    mock_client = MagicMock()
    mock_client.auth.get_user = AsyncMock(return_value=MagicMock(user=None))

    with pytest.raises(ValueError, match="Invalid Supabase JWT"):
        await verify_jwt(mock_client, "bad.jwt.token")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_jwt_falls_back_through_display_name_keys():
    # user_metadata may use 'full_name', 'name', or 'display_name' depending on provider
    mock_user = MagicMock()
    mock_user.id = "user-uuid"
    mock_user.email = "bob@example.com"
    mock_user.user_metadata = {"name": "Bob"}

    mock_client = MagicMock()
    mock_client.auth.get_user = AsyncMock(return_value=MagicMock(user=mock_user))

    result = await verify_jwt(mock_client, "fake.jwt")

    assert result.display_name == "Bob"
