from unittest.mock import AsyncMock, patch

import pytest

from lib.github.auth import get_jurisdictions_sync_headers


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
