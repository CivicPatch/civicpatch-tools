import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import services.browser as shared_browser
import services.polite as polite
from services.browser import resolve_redirect

_FIRST = "https://ecode360.com/UN0123"
_HOP = "https://elsewhere.example.org/charter"


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


def _route(url: str, *, navigation: bool = True) -> MagicMock:
    request = MagicMock(url=url)
    request.is_navigation_request.return_value = navigation
    request.frame.parent_frame = None
    return MagicMock(request=request, continue_=AsyncMock(), abort=AsyncMock())


def _obeying_except_the_hop(failure: Exception | None) -> AsyncMock:
    async def obey_host(url: str) -> None:
        if url == _HOP and failure:
            raise failure

    return AsyncMock(side_effect=obey_host)


@pytest.mark.asyncio
async def test_a_redirect_robots_txt_disallows_is_aborted_and_recorded():
    hop, stopped = _route(_HOP), []

    with patch.object(polite, "obey_host", new=_obeying_except_the_hop(polite.DisallowedByRobots(_HOP))):
        await shared_browser._guard(_FIRST, stopped, hop)

    hop.abort.assert_awaited_once()
    assert isinstance(stopped[0], polite.DisallowedByRobots)


@pytest.mark.asyncio
async def test_an_allowed_redirect_goes_on_and_records_nothing():
    hop, stopped = _route(_HOP), []

    with patch.object(polite, "obey_host", new=_obeying_except_the_hop(None)):
        await shared_browser._guard(_FIRST, stopped, hop)

    hop.continue_.assert_awaited_once()
    assert stopped == []


@pytest.mark.asyncio
async def test_a_private_address_a_page_asks_for_is_aborted_without_blaming_the_page():
    private, stopped = _route("http://10.0.0.5/secret", navigation=False), []

    await shared_browser._guard(_FIRST, stopped, private)

    private.abort.assert_awaited_once()
    assert stopped == []


@pytest.mark.asyncio
async def test_the_first_urls_challenge_reload_takes_no_second_turn():
    first, stopped = _route(_FIRST), []

    with patch.object(polite, "obey_host", new=AsyncMock()) as obeyed:
        await shared_browser._guard(_FIRST, stopped, first)

    obeyed.assert_not_awaited()
    first.continue_.assert_awaited_once()


@pytest.mark.parametrize(
    "content_type,pdf",
    [("application/pdf", True), ("application/PDF; charset=binary", True), ("text/html", False)],
)
def test_a_pdf_is_known_by_its_content_type(content_type: str, pdf: bool):
    assert shared_browser.is_pdf(content_type) is pdf

