import os

import runners.people_collector.steps.step_02_scrape_page.browser as browser
from runners.people_collector.schemas import (
    Link,
    LinkFrontier,
    LinkStatus,
    PeopleCollectorContext,
    PipelineStatus,
)
from runners.people_collector.steps.step_02_scrape_page.scrape_constants import (
    MAX_SCRAPE_ATTEMPTS,
)
from runners.people_collector.steps.step_02_scrape_page.scrape_exceptions import (
    NavigationError,
    NavigationFailureReason,
    RETRYABLE_FAILURE_REASONS,
)
from shared.utils import config_utils, data_path_utils, url_utils
from utils import log_utils


async def scrape_page(
    context: PeopleCollectorContext, link_to_scrape: Link
) -> tuple[LinkFrontier, str]:
    logger = log_utils.get_pipeline_run_logger(context.data.jurisdiction_ocdid)
    logger.info(
        f"Step 2: {PipelineStatus.SCRAPE_PAGE.value}: scraping {link_to_scrape.url}"
    )
    visit_order = _next_visit_order(context.data.frontier)
    frontier = context.data.frontier.dequeue(link_to_scrape.url)

    try:
        folder_name, final_url = await _fetch_and_cache(
            logger, context.data.jurisdiction_ocdid, link_to_scrape.url
        )
    except Exception as e:
        logger.error(f"Error scraping {link_to_scrape.url}: {e}")
        return _record_failure(logger, frontier, link_to_scrape, e, visit_order)

    frontier = frontier.update_link(
        link_to_scrape.url,
        status=LinkStatus.SCRAPED.value,
        folder_name=folder_name,
        visit_order=visit_order,
    )
    return frontier, final_url


def _next_visit_order(frontier: LinkFrontier) -> int:
    return sum(1 for link in frontier.links.values() if link.visit_order is not None) + 1


async def _fetch_and_cache(logger, jurisdiction_ocdid: str, url: str) -> tuple[str, str]:
    html_content, final_url = await browser.scrape(
        logger,
        url,
        {
            "image_directory": data_path_utils.get_images_path(jurisdiction_ocdid),
            "accordion_keywords": config_utils.governance_keywords(),
        },
    )
    if html_content is None:
        raise ValueError("No HTML content retrieved")

    folder_name = url_utils.format_url_to_folder(url)
    page_path = os.path.join(
        data_path_utils.get_cache_path(jurisdiction_ocdid), folder_name
    )
    os.makedirs(page_path, exist_ok=True)
    with open(os.path.join(page_path, "original.html"), "w", encoding="utf-8") as f:
        f.write(html_content)
    return folder_name, final_url


def _record_failure(
    logger, frontier: LinkFrontier, link: Link, error: Exception, visit_order: int
) -> tuple[LinkFrontier, str]:
    failure_reason = error.reason if isinstance(error, NavigationError) else None
    failure_source = error.source if isinstance(error, NavigationError) else None
    attempts = link.attempts + 1

    if should_retry(failure_reason, attempts):
        logger.info(
            f"Requeueing {link.url} after {failure_reason} "
            f"(attempt {attempts} of {MAX_SCRAPE_ATTEMPTS})"
        )
        frontier = frontier.requeue(
            link.url,
            attempts=attempts,
            failure_reason=failure_reason,
            failure_source=failure_source,
        )
        return frontier, link.url

    frontier = frontier.update_link(
        link.url,
        status=LinkStatus.ERROR.value,
        failure_reason=failure_reason,
        failure_source=failure_source,
        visit_order=visit_order,
        attempts=attempts,
    )
    return frontier, link.url


def should_retry(failure_reason: NavigationFailureReason | None, attempts: int) -> bool:
    return attempts < MAX_SCRAPE_ATTEMPTS and failure_reason in RETRYABLE_FAILURE_REASONS
