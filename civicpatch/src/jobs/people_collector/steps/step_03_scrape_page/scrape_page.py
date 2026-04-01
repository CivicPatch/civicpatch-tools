import os
from typing import List, Optional
from shared.utils import data_path_utils, url_utils
import jobs.people_collector.steps.step_03_scrape_page.scrape_utils as scrape_utils
from jobs.people_collector.schemas import (
    PeopleCollectorContext, Link, LinkStatus, WorkflowStatus, DeadUrl
)
from utils import log_utils

_NAVIGATION_FAILURE_MESSAGE = "Failed to load page with all wait strategies"

async def scrape_page(context: PeopleCollectorContext, link_to_scrape: Link) -> tuple[List[Link], Optional[DeadUrl]]:
    """
    Scrape pages based on the links found in the previous search step.
    """
    logger = log_utils.get_workflow_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step 3: {WorkflowStatus.SCRAPE_PAGE.value}: scraping {link_to_scrape.url}")
    jurisdiction_ocdid = context.data.jurisdiction_ocdid

    try:
        image_directory = data_path_utils.get_images_path(jurisdiction_ocdid)
        html_content = await scrape_utils.scrape(logger, link_to_scrape.url, { "image_directory": image_directory })

        if html_content is None:
            raise ValueError("No HTML content retrieved")

        # Save html_content to file under data_source
        cache_path = data_path_utils.get_cache_path(jurisdiction_ocdid)
        folder_name = url_utils.format_url_to_folder(link_to_scrape.url)

        page_path = os.path.join(cache_path, f"{folder_name}")
        os.makedirs(page_path, exist_ok=True)
        page_file_path = os.path.join(page_path, f"original.html")

        with open(page_file_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        # If successful, update the link status to "scraped"
        updated_links = []
        for link in context.data.links:
            if link.url == link_to_scrape.url:
                # Update the status/content for this link
                link.status = LinkStatus.SCRAPED.value
                link.folder_name = folder_name
            updated_links.append(link)
        return updated_links, None
    except Exception as e:
        logger.error(f"Error scraping {link_to_scrape.url}: {e}")
        # If error, update the link status to "error"
        updated_links = []
        for link in context.data.links:
            if link.url == link_to_scrape.url:
                # Update the status/content for this link
                link.status = LinkStatus.ERROR.value
            updated_links.append(link)

        dead_url = DeadUrl(url=link_to_scrape.url, error=str(e)) if _NAVIGATION_FAILURE_MESSAGE in str(e) else None
        return updated_links, dead_url
