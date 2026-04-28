import os
from typing import List
from shared.utils import data_path_utils, url_utils, config_utils
import runners.people_collector.steps.step_02_scrape_page.scrape_utils as scrape_utils
from runners.people_collector.schemas import (
    PeopleCollectorContext, Link, LinkStatus, PipelineStatus
)
from runners.people_collector.steps.step_02_scrape_page.scrape_exceptions import NavigationError
from utils import log_utils

async def scrape_page(context: PeopleCollectorContext, link_to_scrape: Link) -> tuple[List[Link], str]:
    """
    Scrape pages based on the links found in the previous search step.
    """
    logger = log_utils.get_pipeline_run_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step 3: {PipelineStatus.SCRAPE_PAGE.value}: scraping {link_to_scrape.url}")
    jurisdiction_ocdid = context.data.jurisdiction_ocdid

    try:
        image_directory = data_path_utils.get_images_path(jurisdiction_ocdid)
        html_content, final_url = await scrape_utils.scrape(logger, link_to_scrape.url, { "image_directory": image_directory, "accordion_keywords": config_utils.governance_keywords() })

        if html_content is None:
            raise ValueError("No HTML content retrieved")

        # Save html_content to file under data_source
        cache_path = data_path_utils.get_cache_path(jurisdiction_ocdid)
        folder_name = url_utils.format_url_to_folder(final_url)

        page_path = os.path.join(cache_path, f"{folder_name}")
        os.makedirs(page_path, exist_ok=True)
        page_file_path = os.path.join(page_path, f"original.html")

        with open(page_file_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        # If successful, update the link status to "scraped"
        updated_links = [
            link.model_copy(update={"url": final_url, "status": LinkStatus.SCRAPED.value, "folder_name": folder_name})
            if link.url == link_to_scrape.url else link
            for link in context.data.links
        ]
        return updated_links, final_url
    except Exception as e:
        logger.error(f"Error scraping {link_to_scrape.url}: {e}")
        failure_reason = e.reason.value if isinstance(e, NavigationError) else None
        failure_source = e.source if isinstance(e, NavigationError) else None
        updated_links = [
            link.model_copy(update={"status": LinkStatus.ERROR.value, "failure_reason": failure_reason, "failure_source": failure_source})
            if link.url == link_to_scrape.url else link
            for link in context.data.links
        ]
        return updated_links, link_to_scrape.url
