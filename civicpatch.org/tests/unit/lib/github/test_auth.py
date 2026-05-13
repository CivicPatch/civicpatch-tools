import time
from unittest.mock import AsyncMock, patch

import pytest

from lib.github.auth import (
    get_github_token,
    get_jurisdictions_sync_headers,
    get_jurisdictions_sync_token,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_jurisdictions_sync_headers_returns_bearer_token():
    with patch(
        "lib.github.auth.get_jurisdictions_sync_token",
        new_callable=AsyncMock,
        return_value="test-token-abc",
    ):
        headers = await get_jurisdictions_sync_headers()

    assert headers["Authorization"] == "Bearer test-token-abc"
    assert "X-GitHub-Api-Version" in headers


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_github_token_caches_with_refresh_margin():
    """Cached tokens must be invalidated before they actually expire on GitHub's side
    to avoid using a token that dies mid-request."""
    now = time.time()
    expires_at = now + 3600
    mock_set_cached = AsyncMock()
    with (
        patch("lib.github.auth._get_github_config", return_value=("app-id", "key", "inst-id", "url")),
        patch("lib.cache.get_cached", new_callable=AsyncMock, return_value=None),
        patch("lib.github.auth._fetch_github_token", new_callable=AsyncMock, return_value=("tok", expires_at)),
        patch("lib.cache.set_cached", mock_set_cached),
    ):
        await get_github_token()

    mock_set_cached.assert_called_once()
    ttl_arg = mock_set_cached.call_args[0][2]
    assert ttl_arg <= 3300, f"expected ttl ≤ 3300s (3600 - 300 margin), got {ttl_arg}"
    assert ttl_arg > 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_jurisdictions_sync_token_caches_with_refresh_margin():
    now = time.time()
    expires_at = now + 3600
    mock_set_cached = AsyncMock()
    with (
        patch("lib.github.auth._get_jurisdictions_sync_config", return_value=("app-id", "key", "inst-id")),
        patch("lib.cache.get_cached", new_callable=AsyncMock, return_value=None),
        patch(
            "lib.github.auth._fetch_jurisdictions_sync_token",
            new_callable=AsyncMock,
            return_value=("tok", expires_at),
        ),
        patch("lib.cache.set_cached", mock_set_cached),
    ):
        await get_jurisdictions_sync_token()

    mock_set_cached.assert_called_once()
    ttl_arg = mock_set_cached.call_args[0][2]
    assert ttl_arg <= 3300, f"expected ttl ≤ 3300s (3600 - 300 margin), got {ttl_arg}"
    assert ttl_arg > 0
