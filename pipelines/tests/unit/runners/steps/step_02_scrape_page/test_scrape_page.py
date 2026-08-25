"""
Unit tests for scrape_page step logic.

These mock browser.scrape so the full pipeline can be tested without a real browser.
"""
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from runners.people_collector.schemas import LinkFrontier, LinkStatus
from runners.people_collector.steps.step_02_scrape_page.scrape_constants import MAX_SCRAPE_ATTEMPTS
from runners.people_collector.steps.step_02_scrape_page.scrape_page import scrape_page
from runners.people_collector.steps.step_02_scrape_page.scrape_exceptions import NavigationError, NavigationFailureReason
from tests.factories.pipeline_run_context import pipeline_run_context_factory

pytestmark = pytest.mark.unit

PAGE_URL = "https://example.gov/council"
HTML = "<html><body><p>Council members</p></body></html>"

MODULE = "runners.people_collector.steps.step_02_scrape_page.scrape_page"


def _make_context(url: str = PAGE_URL):
    frontier = LinkFrontier.from_urls([url])
    ctx = pipeline_run_context_factory(steps={})
    return ctx.model_copy(update={"data": ctx.data.model_copy(update={"frontier": frontier})})


def _patches(html=HTML, final_url=PAGE_URL, tmp_path=None):
    cache = str(tmp_path) if tmp_path else "/tmp/cache"
    return [
        patch(f"{MODULE}.browser.scrape", new=AsyncMock(return_value=(html, final_url))),
        patch(f"{MODULE}.data_path_utils.get_cache_path", return_value=cache),
        patch(f"{MODULE}.data_path_utils.get_images_path", return_value="/tmp/images"),
        patch(f"{MODULE}.config_utils.governance_keywords", return_value=[]),
        patch(f"{MODULE}.os.makedirs"),
        patch("builtins.open", MagicMock()),
    ]


@pytest.mark.asyncio
async def test_scrape_page_marks_link_as_scraped(tmp_path):
    ctx = _make_context()
    link = ctx.data.frontier.next_pending()
    with patch(f"{MODULE}.browser.scrape", new=AsyncMock(return_value=(HTML, PAGE_URL))), \
         patch(f"{MODULE}.data_path_utils.get_cache_path", return_value=str(tmp_path)), \
         patch(f"{MODULE}.data_path_utils.get_images_path", return_value=str(tmp_path)), \
         patch(f"{MODULE}.config_utils.governance_keywords", return_value=[]):
        frontier, _ = await scrape_page(ctx, link)
    assert frontier.get(PAGE_URL).status == LinkStatus.SCRAPED.value


@pytest.mark.asyncio
async def test_scrape_page_url_not_updated_on_redirect(tmp_path):
    """url field must stay as link_to_scrape.url even when the page redirects."""
    redirect_url = PAGE_URL + "?did=16"
    ctx = _make_context()
    link = ctx.data.frontier.next_pending()
    with patch(f"{MODULE}.browser.scrape", new=AsyncMock(return_value=(HTML, redirect_url))), \
         patch(f"{MODULE}.data_path_utils.get_cache_path", return_value=str(tmp_path)), \
         patch(f"{MODULE}.data_path_utils.get_images_path", return_value=str(tmp_path)), \
         patch(f"{MODULE}.config_utils.governance_keywords", return_value=[]):
        frontier, final_url = await scrape_page(ctx, link)
    scraped = frontier.get(PAGE_URL)
    assert scraped is not None, "link should still be findable at original URL key"
    assert scraped.status == LinkStatus.SCRAPED.value
    assert scraped.url == PAGE_URL, "url field must not be updated to redirect destination"
    assert final_url == redirect_url


@pytest.mark.asyncio
async def test_scrape_page_folder_name_based_on_original_url(tmp_path):
    redirect_url = PAGE_URL + "?session=abc"
    ctx = _make_context()
    link = ctx.data.frontier.next_pending()
    from shared.utils.url_utils import format_url_to_folder
    expected_folder = format_url_to_folder(PAGE_URL)
    with patch(f"{MODULE}.browser.scrape", new=AsyncMock(return_value=(HTML, redirect_url))), \
         patch(f"{MODULE}.data_path_utils.get_cache_path", return_value=str(tmp_path)), \
         patch(f"{MODULE}.data_path_utils.get_images_path", return_value=str(tmp_path)), \
         patch(f"{MODULE}.config_utils.governance_keywords", return_value=[]):
        frontier, _ = await scrape_page(ctx, link)
    assert frontier.get(PAGE_URL).folder_name == expected_folder


@pytest.mark.asyncio
async def test_scrape_page_removes_from_queue(tmp_path):
    ctx = _make_context()
    assert len(ctx.data.frontier.queue) == 1
    link = ctx.data.frontier.next_pending()
    with patch(f"{MODULE}.browser.scrape", new=AsyncMock(return_value=(HTML, PAGE_URL))), \
         patch(f"{MODULE}.data_path_utils.get_cache_path", return_value=str(tmp_path)), \
         patch(f"{MODULE}.data_path_utils.get_images_path", return_value=str(tmp_path)), \
         patch(f"{MODULE}.config_utils.governance_keywords", return_value=[]):
        frontier, _ = await scrape_page(ctx, link)
    assert len(frontier.queue) == 0


@pytest.mark.asyncio
async def test_scrape_page_sets_visit_order(tmp_path):
    ctx = _make_context()
    link = ctx.data.frontier.next_pending()
    with patch(f"{MODULE}.browser.scrape", new=AsyncMock(return_value=(HTML, PAGE_URL))), \
         patch(f"{MODULE}.data_path_utils.get_cache_path", return_value=str(tmp_path)), \
         patch(f"{MODULE}.data_path_utils.get_images_path", return_value=str(tmp_path)), \
         patch(f"{MODULE}.config_utils.governance_keywords", return_value=[]):
        frontier, _ = await scrape_page(ctx, link)
    assert frontier.get(PAGE_URL).visit_order == 1


@pytest.mark.asyncio
async def test_scrape_page_marks_error_on_navigation_failure(tmp_path):
    ctx = _make_context()
    link = ctx.data.frontier.next_pending()
    err = NavigationError(PAGE_URL, NavigationFailureReason.NET_DNS_FAILURE, source="DNS")
    with patch(f"{MODULE}.browser.scrape", new=AsyncMock(side_effect=err)), \
         patch(f"{MODULE}.data_path_utils.get_cache_path", return_value=str(tmp_path)), \
         patch(f"{MODULE}.data_path_utils.get_images_path", return_value=str(tmp_path)), \
         patch(f"{MODULE}.config_utils.governance_keywords", return_value=[]):
        frontier, returned_url = await scrape_page(ctx, link)
    scraped = frontier.get(PAGE_URL)
    assert scraped.status == LinkStatus.ERROR.value
    assert scraped.failure_reason == NavigationFailureReason.NET_DNS_FAILURE.value
    assert scraped.failure_source == "DNS"
    assert returned_url == PAGE_URL


@pytest.mark.asyncio
async def test_scrape_page_requeues_transient_failure(tmp_path):
    ctx = _make_context()
    link = ctx.data.frontier.next_pending()
    err = NavigationError(PAGE_URL, NavigationFailureReason.NET_TIMEOUT, source="TIMEOUT")
    with patch(f"{MODULE}.browser.scrape", new=AsyncMock(side_effect=err)), \
         patch(f"{MODULE}.data_path_utils.get_cache_path", return_value=str(tmp_path)), \
         patch(f"{MODULE}.data_path_utils.get_images_path", return_value=str(tmp_path)), \
         patch(f"{MODULE}.config_utils.governance_keywords", return_value=[]):
        frontier, _ = await scrape_page(ctx, link)
    retried = frontier.get(PAGE_URL)
    assert retried.status == LinkStatus.PENDING.value
    assert retried.attempts == 1
    assert frontier.next_pending().url == PAGE_URL


@pytest.mark.asyncio
async def test_requeued_link_goes_behind_pages_already_pending(tmp_path):
    other_url = "https://example.gov/mayor"
    frontier = LinkFrontier.from_urls([PAGE_URL, other_url])
    ctx = pipeline_run_context_factory(steps={})
    ctx = ctx.model_copy(update={"data": ctx.data.model_copy(update={"frontier": frontier})})
    link = frontier.get(PAGE_URL)
    err = NavigationError(PAGE_URL, NavigationFailureReason.NET_TIMEOUT, source="TIMEOUT")
    with patch(f"{MODULE}.browser.scrape", new=AsyncMock(side_effect=err)), \
         patch(f"{MODULE}.data_path_utils.get_cache_path", return_value=str(tmp_path)), \
         patch(f"{MODULE}.data_path_utils.get_images_path", return_value=str(tmp_path)), \
         patch(f"{MODULE}.config_utils.governance_keywords", return_value=[]):
        result, _ = await scrape_page(ctx, link)
    assert result.next_pending().url == other_url


@pytest.mark.asyncio
async def test_scrape_page_gives_up_on_transient_failure_after_final_attempt(tmp_path):
    ctx = _make_context()
    spent = ctx.data.frontier.update_link(PAGE_URL, attempts=MAX_SCRAPE_ATTEMPTS - 1)
    ctx = ctx.model_copy(update={"data": ctx.data.model_copy(update={"frontier": spent})})
    link = ctx.data.frontier.next_pending()
    err = NavigationError(PAGE_URL, NavigationFailureReason.NET_TIMEOUT, source="TIMEOUT")
    with patch(f"{MODULE}.browser.scrape", new=AsyncMock(side_effect=err)), \
         patch(f"{MODULE}.data_path_utils.get_cache_path", return_value=str(tmp_path)), \
         patch(f"{MODULE}.data_path_utils.get_images_path", return_value=str(tmp_path)), \
         patch(f"{MODULE}.config_utils.governance_keywords", return_value=[]):
        frontier, _ = await scrape_page(ctx, link)
    exhausted = frontier.get(PAGE_URL)
    assert exhausted.status == LinkStatus.ERROR.value
    assert exhausted.attempts == MAX_SCRAPE_ATTEMPTS
    assert frontier.queue == []


@pytest.mark.asyncio
async def test_scrape_page_preserves_other_links(tmp_path):
    other_url = "https://example.gov/mayor"
    frontier = LinkFrontier.from_urls([PAGE_URL, other_url])
    ctx = pipeline_run_context_factory(steps={})
    ctx = ctx.model_copy(update={"data": ctx.data.model_copy(update={"frontier": frontier})})
    link = frontier.get(PAGE_URL)
    with patch(f"{MODULE}.browser.scrape", new=AsyncMock(return_value=(HTML, PAGE_URL))), \
         patch(f"{MODULE}.data_path_utils.get_cache_path", return_value=str(tmp_path)), \
         patch(f"{MODULE}.data_path_utils.get_images_path", return_value=str(tmp_path)), \
         patch(f"{MODULE}.config_utils.governance_keywords", return_value=[]):
        result_frontier, _ = await scrape_page(ctx, link)
    assert result_frontier.get(other_url).status == LinkStatus.PENDING.value
