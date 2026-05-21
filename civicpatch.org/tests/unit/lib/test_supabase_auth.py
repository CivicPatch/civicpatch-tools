from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.supabase_auth import SupabaseUser, create_supabase_client, to_supabase_user


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
def test_to_supabase_user_extracts_full_name():
    user = MagicMock()
    user.id = "user-uuid"
    user.email = "alice@example.com"
    user.user_metadata = {"full_name": "Alice"}

    result = to_supabase_user(user)

    assert result == SupabaseUser(
        id="user-uuid", email="alice@example.com", display_name="Alice"
    )
    assert result.provider == "supabase"


@pytest.mark.unit
def test_to_supabase_user_falls_back_through_display_name_keys():
    # user_metadata may use 'full_name', 'name', or 'display_name' depending on provider
    user = MagicMock()
    user.id = "u"
    user.email = "bob@example.com"
    user.user_metadata = {"name": "Bob"}

    result = to_supabase_user(user)

    assert result.display_name == "Bob"


@pytest.mark.unit
def test_to_supabase_user_returns_none_display_name_when_metadata_empty():
    user = MagicMock()
    user.id = "u"
    user.email = "anon@example.com"
    user.user_metadata = {}

    result = to_supabase_user(user)

    assert result.display_name is None
