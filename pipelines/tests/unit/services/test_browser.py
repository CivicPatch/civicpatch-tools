import pytest
from unittest.mock import AsyncMock, patch

from services.browser import resolve_redirect


def _make_playwright_mock(final_url: str):
    page = AsyncMock()
    page.url = final_url
    page.goto = AsyncMock()

    browser = AsyncMock()
    browser.new_page = AsyncMock(return_value=page)
    browser.close = AsyncMock()
    browser.__aenter__ = AsyncMock(return_value=browser)
    browser.__aexit__ = AsyncMock(return_value=None)

    chromium = AsyncMock()
    chromium.launch_persistent_context = AsyncMock(return_value=browser)

    playwright = AsyncMock()
    playwright.chromium = chromium
    playwright.__aenter__ = AsyncMock(return_value=playwright)
    playwright.__aexit__ = AsyncMock(return_value=None)

    return playwright


@pytest.mark.asyncio
async def test_resolve_redirect_follows_redirect():
    mock_playwright = _make_playwright_mock("https://new-city.gov/")
    with patch("services.browser.async_playwright", return_value=mock_playwright):
        result = await resolve_redirect("https://old-city.gov/")
    assert result == "https://new-city.gov/"


@pytest.mark.asyncio
async def test_resolve_redirect_no_redirect():
    mock_playwright = _make_playwright_mock("https://city.gov/")
    with patch("services.browser.async_playwright", return_value=mock_playwright):
        result = await resolve_redirect("https://city.gov/")
    assert result == "https://city.gov/"


@pytest.mark.asyncio
async def test_resolve_redirect_falls_back_on_error():
    with patch("services.browser.async_playwright", side_effect=Exception("timeout")):
        result = await resolve_redirect("https://city.gov/")
    assert result == "https://city.gov/"