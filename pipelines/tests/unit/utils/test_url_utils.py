import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from utils.url_utils import resolve_redirect


@pytest.mark.asyncio
async def test_resolve_redirect_follows_redirect():
    mock_response = MagicMock()
    mock_response.url = "https://new-city.gov/"

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.head = AsyncMock(return_value=mock_response)

    with patch("utils.url_utils.httpx.AsyncClient", return_value=mock_client):
        result = await resolve_redirect("https://old-city.gov/")

    assert result == "https://new-city.gov/"


@pytest.mark.asyncio
async def test_resolve_redirect_no_redirect():
    mock_response = MagicMock()
    mock_response.url = "https://city.gov/"

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.head = AsyncMock(return_value=mock_response)

    with patch("utils.url_utils.httpx.AsyncClient", return_value=mock_client):
        result = await resolve_redirect("https://city.gov/")

    assert result == "https://city.gov/"


@pytest.mark.asyncio
async def test_resolve_redirect_falls_back_on_network_error():
    with patch("utils.url_utils.httpx.AsyncClient", side_effect=Exception("timeout")):
        result = await resolve_redirect("https://city.gov/")

    assert result == "https://city.gov/"


@pytest.mark.asyncio
async def test_resolve_redirect_falls_back_on_http_error():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.head = AsyncMock(side_effect=Exception("connection refused"))

    with patch("utils.url_utils.httpx.AsyncClient", return_value=mock_client):
        result = await resolve_redirect("https://city.gov/")

    assert result == "https://city.gov/"
