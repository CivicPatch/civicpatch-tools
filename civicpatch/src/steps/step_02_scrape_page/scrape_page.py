import os
import utils.scrape_utils as scrape_utils
from schemas import PipelineContext, Link, LinkStatus
import utils.data_path_utils as data_path_utils
import utils.url_utils as url_utils

def scrape_page(context: PipelineContext, link_to_scrape: Link):
    """
    Scrape pages based on the links found in the previous search step.
    """
    print(f"Scraping page: {link_to_scrape['url']} for state: {context['state']}, GEOID: {context['geoid']}")
    html_content = scrape_utils.scrape(link_to_scrape["url"], {})

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
            updated_links.append({**link, "status": LinkStatus.SCRAPED.value})
        else:
            updated_links.append(link)
    return {
        "links": updated_links
    }
