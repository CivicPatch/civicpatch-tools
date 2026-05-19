from unittest.mock import MagicMock, patch

import pytest

from lib.supabase_auth import SupabaseUser, get_supabase_client, verify_jwt


@pytest.mark.unit
def test_get_supabase_client_raises_when_env_missing():
    with patch(
        "lib.supabase_auth.environment.get_env_vars",
        return_value={"SUPABASE_URL": None, "SUPABASE_SECRET_KEY": None},
    ):
        with pytest.raises(ValueError, match="not configured"):
            get_supabase_client()


@pytest.mark.unit
def test_get_supabase_client_builds_client_when_configured():
    with (
        patch(
            "lib.supabase_auth.environment.get_env_vars",
            return_value={
                "SUPABASE_URL": "https://example.supabase.co",
                "SUPABASE_SECRET_KEY": "sb_secret_test",
            },
        ),
        patch("lib.supabase_auth.create_client") as mock_create,
    ):
        mock_create.return_value = MagicMock()
        client = get_supabase_client()

    mock_create.assert_called_once_with(
        "https://example.supabase.co", "sb_secret_test"
    )
    assert client is mock_create.return_value


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_jwt_returns_supabase_user_on_success():
    mock_user = MagicMock()
    mock_user.id = "user-uuid"
    mock_user.email = "alice@example.com"
    mock_user.user_metadata = {"full_name": "Alice"}

    mock_client = MagicMock()
    mock_client.auth.get_user = MagicMock(return_value=MagicMock(user=mock_user))

    result = await verify_jwt(mock_client, "fake.jwt.token")

    assert result == SupabaseUser(
        id="user-uuid", email="alice@example.com", display_name="Alice"
    )
    assert result.provider == "supabase"
    mock_client.auth.get_user.assert_called_once_with("fake.jwt.token")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_jwt_raises_when_user_is_none():
    mock_client = MagicMock()
    mock_client.auth.get_user = MagicMock(return_value=MagicMock(user=None))

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
    mock_client.auth.get_user = MagicMock(return_value=MagicMock(user=mock_user))

    result = await verify_jwt(mock_client, "fake.jwt")

    assert result.display_name == "Bob"
