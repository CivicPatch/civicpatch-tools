from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runners.pipeline03_people_collector.schemas import (
    LinkFrontier,
    LinkStatus,
    PreprocessPageContentStep,
    ProcessPageContentStep,
)
from runners.pipeline03_people_collector.steps.step_02_crawl_page.crawl_page import crawl_page
from tests.factories.pipeline_run_context import pipeline_run_context_factory

pytestmark = pytest.mark.unit

PAGE_URL = "https://example.gov/council"
FINAL_URL = "https://example.gov/council/"
FOLDER = "example_gov_council"
MODULE = "runners.pipeline03_people_collector.steps.step_02_crawl_page.crawl_page"
PREPROCESSED = PreprocessPageContentStep(elapsed_times=[1])
PROCESSED = ProcessPageContentStep(records={})
BEFORE_THE_PAGE = ProcessPageContentStep(records={"Earlier Person": []})


def _context():
    context = pipeline_run_context_factory(steps={})
    frontier = LinkFrontier.from_urls([PAGE_URL])
    data = context.data.model_copy(update={"frontier": frontier, "process_page_content_step": BEFORE_THE_PAGE})
    return context.model_copy(update={"data": data})


def _scrape_to(status: LinkStatus):
    async def scrape(context, page):
        frontier = context.data.frontier.dequeue(page.url).update_link(
            page.url, status=status.value, folder_name=FOLDER
        )
        return frontier, FINAL_URL

    return scrape


def _preprocess_to(status: LinkStatus):
    def preprocess(context, page):
        return context.data.frontier.update_link(page.url, status=status.value), PREPROCESSED

    return preprocess


async def _process(context, page):
    return context.data.frontier.update_link(page.url, status=LinkStatus.DONE.value), PROCESSED


def _patches(scrape, preprocess, process):
    return (
        patch(f"{MODULE}.scrape_page", new=scrape),
        patch(f"{MODULE}.preprocess_page_content", new=preprocess),
        patch(f"{MODULE}.process_page_content", new=process),
    )


async def _crawl(scrape, preprocess, process):
    context = _context()
    page = context.data.frontier.get(PAGE_URL)
    scrape_patch, preprocess_patch, process_patch = _patches(scrape, preprocess, process)
    with scrape_patch, preprocess_patch, process_patch:
        return await crawl_page(context, page)


@pytest.mark.asyncio
async def test_a_page_that_failed_to_scrape_goes_no_further():
    preprocess = MagicMock()
    process = AsyncMock()

    result = await _crawl(_scrape_to(LinkStatus.ERROR), preprocess, process)

    preprocess.assert_not_called()
    process.assert_not_called()
    assert result.frontier.status_of(PAGE_URL) == LinkStatus.ERROR
    assert result.preprocess_page_content_step is None
    assert result.process_page_content_step == BEFORE_THE_PAGE


@pytest.mark.asyncio
async def test_a_page_with_no_content_is_not_processed():
    process = AsyncMock()

    result = await _crawl(
        _scrape_to(LinkStatus.SCRAPED), _preprocess_to(LinkStatus.PREPROCESSED_NO_CONTENT), process
    )

    process.assert_not_called()
    assert result.frontier.status_of(PAGE_URL) == LinkStatus.PREPROCESSED_NO_CONTENT
    assert result.preprocess_page_content_step == PREPROCESSED
    assert result.process_page_content_step == BEFORE_THE_PAGE


@pytest.mark.asyncio
async def test_a_page_with_content_runs_every_step():
    result = await _crawl(_scrape_to(LinkStatus.SCRAPED), _preprocess_to(LinkStatus.PREPROCESSED), _process)

    assert result.frontier.status_of(PAGE_URL) == LinkStatus.DONE
    assert result.final_url == FINAL_URL
    assert result.preprocess_page_content_step == PREPROCESSED
    assert result.process_page_content_step == PROCESSED


@pytest.mark.asyncio
async def test_each_step_gets_the_link_and_frontier_the_last_step_left():
    seen = []

    def preprocess(context, page):
        seen.append((page.folder_name, context.data.frontier.status_of(PAGE_URL)))
        return _preprocess_to(LinkStatus.PREPROCESSED)(context, page)

    await _crawl(_scrape_to(LinkStatus.SCRAPED), preprocess, _process)

    assert seen == [(FOLDER, LinkStatus.SCRAPED)]
