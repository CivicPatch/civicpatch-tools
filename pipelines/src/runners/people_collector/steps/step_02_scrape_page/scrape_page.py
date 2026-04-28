import os
from shared.utils import data_path_utils, url_utils, config_utils
import runners.people_collector.steps.step_02_scrape_page.browser as browser
from runners.people_collector.schemas import (
    PeopleCollectorContext, Link, LinkFrontier, LinkStatus, PipelineStatus
)
from runners.people_collector.steps.step_02_scrape_page.scrape_exceptions import NavigationError
from utils import log_utils


async def scrape_page(context: PeopleCollectorContext, link_to_scrape: Link) -> tuple[LinkFrontier, str]:
    logger = log_utils.get_pipeline_run_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step 3: {PipelineStatus.SCRAPE_PAGE.value}: scraping {link_to_scrape.url}")
    jurisdiction_ocdid = context.data.jurisdiction_ocdid

    visit_order = sum(1 for l in context.data.frontier.links.values() if l.visit_order is not None) + 1
    frontier = context.data.frontier.dequeue(link_to_scrape.url)

    try:
        image_directory = data_path_utils.get_images_path(jurisdiction_ocdid)
        html_content, final_url = await browser.scrape(logger, link_to_scrape.url, { "image_directory": image_directory, "accordion_keywords": config_utils.governance_keywords() })

        if html_content is None:
            raise ValueError("No HTML content retrieved")

        cache_path = data_path_utils.get_cache_path(jurisdiction_ocdid)
        folder_name = url_utils.format_url_to_folder(link_to_scrape.url)

        page_path = os.path.join(cache_path, f"{folder_name}")
        os.makedirs(page_path, exist_ok=True)
        with open(os.path.join(page_path, "original.html"), "w", encoding="utf-8") as f:
            f.write(html_content)

        frontier = frontier.update_link(
            link_to_scrape.url,
            url=final_url,
            status=LinkStatus.SCRAPED.value,
            folder_name=folder_name,
            visit_order=visit_order,
        )
        return frontier, final_url

    except Exception as e:
        logger.error(f"Error scraping {link_to_scrape.url}: {e}")
        failure_reason = e.reason.value if isinstance(e, NavigationError) else None
        failure_source = e.source if isinstance(e, NavigationError) else None
        frontier = frontier.update_link(
            link_to_scrape.url,
            status=LinkStatus.ERROR.value,
            failure_reason=failure_reason,
            failure_source=failure_source,
            visit_order=visit_order,
        )
        return frontier, link_to_scrape.url
