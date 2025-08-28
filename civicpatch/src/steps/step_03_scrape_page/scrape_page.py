import os
import utils.scrape_utils as scrape_utils
from schemas import PipelineContext, Link, LinkStatus, PipelineStatus
import utils.data_path_utils as data_path_utils
import utils.url_utils as url_utils

async def scrape_page(context: PipelineContext, link_to_scrape: Link):
    """
    Scrape pages based on the links found in the previous search step.
    """
    print(f"Step 3: {PipelineStatus.SCRAPE_PAGE.value}")

    image_directory = data_path_utils.get_images_path(context["state"], context["geoid"])
    html_content = await scrape_utils.scrape(link_to_scrape["url"], { "image_directory": image_directory })

    # Save html_content to file under data_source
    cache_path = data_path_utils.get_cache_path(context["state"], context["geoid"])
    folder_name = url_utils.format_url_to_folder(link_to_scrape["url"])

    page_path = os.path.join(cache_path, f"{folder_name}")
    os.makedirs(page_path, exist_ok=True)
    page_file_path = os.path.join(page_path, f"original.html")

    with open(page_file_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    # If successful, update the link status to "scraped"
    updated_links = []
    for link in context["links"]:
        if link["url"] == link_to_scrape["url"]:
            # Update the status/content for this link
            updated_links.append({**link, "status": LinkStatus.SCRAPED.value, "folder_name": folder_name})
        else:
            updated_links.append(link)
    return {
        "links": updated_links
    }
