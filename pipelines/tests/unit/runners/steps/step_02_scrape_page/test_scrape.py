import pytest
from unittest.mock import AsyncMock, MagicMock, call, patch

from runners.pipeline03_people_collector.steps.step_02_scrape_page import browser as browser_module
from runners.pipeline03_people_collector.steps.step_02_scrape_page.scrape_exceptions import (
    NavigationError,
    NavigationFailureReason,
)

pytestmark = pytest.mark.unit

MODULE = "runners.pipeline03_people_collector.steps.step_02_scrape_page.browser"


def _make_playwright_stack(page_url="https://example.com"):
    response = MagicMock()
    response.ok = True
    response.status = 200
    response.headers = {}

    page = MagicMock()
    page.url = page_url
    page.goto = AsyncMock(return_value=response)
    page.content = AsyncMock(return_value="<html></html>")
    page.set_default_timeout = MagicMock()
    page.on = MagicMock()

    browser = MagicMock()
    browser.new_page = AsyncMock(return_value=page)
    browser.close = AsyncMock()

    chromium = MagicMock()
    chromium.launch_persistent_context = AsyncMock(return_value=browser)

    playwright_instance = MagicMock()
    playwright_instance.chromium = chromium

    playwright_cm = MagicMock()
    playwright_cm.__aenter__ = AsyncMock(return_value=playwright_instance)
    playwright_cm.__aexit__ = AsyncMock(return_value=False)

    browser_cm = MagicMock()
    browser_cm.__aenter__ = AsyncMock(return_value=browser)
    browser_cm.__aexit__ = AsyncMock(return_value=False)
    chromium.launch_persistent_context.return_value = browser

    return playwright_cm, playwright_instance, browser, page, response


@pytest.mark.asyncio
async def test_scrape_calls_all_helpers_in_order():
    from runners.pipeline03_people_collector.steps.step_02_scrape_page.browser import scrape

    playwright_cm, _, browser, page, _ = _make_playwright_stack()
    call_order = []

    with (
        patch(f"{MODULE}.async_playwright", return_value=playwright_cm),
        patch(f"{MODULE}.auto_detect_and_wait", new=AsyncMock(side_effect=lambda *a, **kw: call_order.append("auto_detect_and_wait"))) as mock_auto,
        patch(f"{MODULE}.expand_accordions",   new=AsyncMock(side_effect=lambda *a, **kw: call_order.append("expand_accordions"))) as mock_expand,
        patch(f"{MODULE}.flatten_shadow_root", new=AsyncMock(side_effect=lambda *a, **kw: call_order.append("flatten_shadow_root"))) as mock_flatten,
        patch(f"{MODULE}.html_relative_to_absolute_urls", new=AsyncMock(side_effect=lambda *a, **kw: call_order.append("html_relative_to_absolute_urls"))) as mock_abs,
        patch(f"{MODULE}.inline_iframes",      new=AsyncMock(side_effect=lambda *a, **kw: call_order.append("inline_iframes"))) as mock_inline,
    ):
        logger = MagicMock()
        await scrape(logger, "https://example.com")

    assert call_order == [
        "auto_detect_and_wait",
        "expand_accordions",
        "flatten_shadow_root",
        "html_relative_to_absolute_urls",
        "inline_iframes",
    ]


@pytest.mark.asyncio
async def test_scrape_passes_accordion_keywords_to_expand_accordions():
    from runners.pipeline03_people_collector.steps.step_02_scrape_page.browser import scrape

    playwright_cm, _, browser, page, _ = _make_playwright_stack()
    keywords = ["council", "mayor"]

    with (
        patch(f"{MODULE}.async_playwright", return_value=playwright_cm),
        patch(f"{MODULE}.auto_detect_and_wait", new=AsyncMock()),
        patch(f"{MODULE}.expand_accordions", new=AsyncMock()) as mock_expand,
        patch(f"{MODULE}.flatten_shadow_root", new=AsyncMock()),
        patch(f"{MODULE}.html_relative_to_absolute_urls", new=AsyncMock()),
        patch(f"{MODULE}.inline_iframes", new=AsyncMock()),
    ):
        logger = MagicMock()
        await scrape(logger, "https://example.com", options={"accordion_keywords": keywords})

    mock_expand.assert_awaited_once()
    assert mock_expand.call_args[0][2] == keywords


@pytest.mark.asyncio
async def test_scrape_calls_expand_accordions_with_none_when_no_keywords():
    from runners.pipeline03_people_collector.steps.step_02_scrape_page.browser import scrape

    playwright_cm, _, browser, page, _ = _make_playwright_stack()

    with (
        patch(f"{MODULE}.async_playwright", return_value=playwright_cm),
        patch(f"{MODULE}.auto_detect_and_wait", new=AsyncMock()),
        patch(f"{MODULE}.expand_accordions", new=AsyncMock()) as mock_expand,
        patch(f"{MODULE}.flatten_shadow_root", new=AsyncMock()),
        patch(f"{MODULE}.html_relative_to_absolute_urls", new=AsyncMock()),
        patch(f"{MODULE}.inline_iframes", new=AsyncMock()),
    ):
        logger = MagicMock()
        await scrape(logger, "https://example.com")

    mock_expand.assert_awaited_once()
    assert mock_expand.call_args[0][2] is None


@pytest.mark.asyncio
async def test_scrape_calls_download_images_when_image_directory_provided():
    from runners.pipeline03_people_collector.steps.step_02_scrape_page.browser import scrape

    playwright_cm, _, browser, page, _ = _make_playwright_stack()

    with (
        patch(f"{MODULE}.async_playwright", return_value=playwright_cm),
        patch(f"{MODULE}.auto_detect_and_wait", new=AsyncMock()),
        patch(f"{MODULE}.expand_accordions", new=AsyncMock()),
        patch(f"{MODULE}.flatten_shadow_root", new=AsyncMock()),
        patch(f"{MODULE}.html_relative_to_absolute_urls", new=AsyncMock()),
        patch(f"{MODULE}.inline_iframes", new=AsyncMock()),
        patch(f"{MODULE}.download_images", new=AsyncMock()) as mock_dl,
    ):
        logger = MagicMock()
        await scrape(logger, "https://example.com", options={"image_directory": "/tmp/imgs"})

    mock_dl.assert_awaited_once()
    assert mock_dl.call_args[0][3] == "/tmp/imgs"


@pytest.mark.asyncio
async def test_scrape_skips_download_images_when_no_image_directory():
    from runners.pipeline03_people_collector.steps.step_02_scrape_page.browser import scrape

    playwright_cm, _, browser, page, _ = _make_playwright_stack()

    with (
        patch(f"{MODULE}.async_playwright", return_value=playwright_cm),
        patch(f"{MODULE}.auto_detect_and_wait", new=AsyncMock()),
        patch(f"{MODULE}.expand_accordions", new=AsyncMock()),
        patch(f"{MODULE}.flatten_shadow_root", new=AsyncMock()),
        patch(f"{MODULE}.html_relative_to_absolute_urls", new=AsyncMock()),
        patch(f"{MODULE}.inline_iframes", new=AsyncMock()),
        patch(f"{MODULE}.download_images", new=AsyncMock()) as mock_dl,
    ):
        logger = MagicMock()
        await scrape(logger, "https://example.com")

    mock_dl.assert_not_awaited()


def _navigation_error(url: str, reason):
    return NavigationError(url, reason, source="")


@pytest.mark.parametrize(
    ("url", "reason", "retried"),
    [
        ("http://townofbonanza.com/", "navigation_failure_net_blocked_by_client", True),
        ("http://townofbonanza.com/", "navigation_failure_net_timeout", False),
        ("https://townofbonanza.com/", "navigation_failure_net_blocked_by_client", False),
    ],
)
def test_only_an_http_url_blocked_by_chrome_is_retried_without_the_https_upgrade(url, reason, retried):
    assert browser_module._blocked_by_https_upgrade(_navigation_error(url, NavigationFailureReason(reason)), url) is retried


@pytest.mark.asyncio
async def test_a_page_chrome_blocked_is_opened_again_without_the_https_upgrade():
    url = "http://townofbonanza.com/"
    playwright_cm, _, browser, page, response = _make_playwright_stack(url)
    blocked = _navigation_error(url, NavigationFailureReason.NET_BLOCKED_BY_CLIENT)
    opened = AsyncMock(side_effect=[blocked, (browser, page, response)])

    with (
        patch(f"{MODULE}.async_playwright", return_value=playwright_cm),
        patch(f"{MODULE}._open", new=opened),
        patch(f"{MODULE}.auto_detect_and_wait", new=AsyncMock()),
        patch(f"{MODULE}.expand_accordions", new=AsyncMock()),
        patch(f"{MODULE}.flatten_shadow_root", new=AsyncMock()),
        patch(f"{MODULE}.html_relative_to_absolute_urls", new=AsyncMock()),
        patch(f"{MODULE}.inline_iframes", new=AsyncMock()),
    ):
        await browser_module.scrape(MagicMock(), url)

    assert [c.kwargs["launch_args"] for c in opened.await_args_list] == [[], [browser_module.NO_HTTPS_UPGRADE]]


@pytest.mark.asyncio
async def test_a_page_still_blocked_without_the_https_upgrade_is_not_tried_a_third_time():
    url = "http://townofbonanza.com/"
    playwright_cm, *_ = _make_playwright_stack(url)
    blocked = _navigation_error(url, NavigationFailureReason.NET_BLOCKED_BY_CLIENT)
    opened = AsyncMock(side_effect=[blocked, blocked])

    with (
        patch(f"{MODULE}.async_playwright", return_value=playwright_cm),
        patch(f"{MODULE}._open", new=opened),
        pytest.raises(NavigationError),
    ):
        await browser_module.scrape(MagicMock(), url)

    assert opened.await_count == 2
