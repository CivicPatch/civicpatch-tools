import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from jobs.people_collector.steps.step_03_scrape_page.scrape_utils import scrape
from jobs.people_collector.steps.step_04_preprocess_page_content.entity_extraction import sort_urls_by_keyword_similarity
from typing import Tuple

SEARCH_PAGE_LIMIT = 10

async def crawl(logger, keywords, site_search):
    """
    Perform a brute force search using the provided search query and site search.

    Args:
        _search_query (str): Unused. Let's hope the entire sitemap is within the first 20-ish pages
        keywords (list): A list of keywords to search for.
        site_search (str): A specific site to limit the search to.

    Returns:
        list: A list of URLs found during the search.
    """
    if not site_search:
        raise ValueError("The 'site_search' parameter is required.")

    visited = set()
    queue = [site_search]
    results = []

    while queue:
        logger.info(f"Crawl queue length: {len(queue)}")
        if len(visited) >= SEARCH_PAGE_LIMIT:
            break

        current_url = queue.pop(0)
        logger.info(f"Crawling URL: {current_url}")
        if current_url in visited:
            continue

        visited.add(current_url)
        try:
            response_html = await scrape(logger, current_url)
            if response_html is None:
                logger.warning(f"Failed to scrape {current_url}")
                continue

            soup = BeautifulSoup(response_html, "html.parser")
            for link in soup.find_all("a", href=True):
                href = link["href"]
                full_url = urljoin(current_url, href)

                # Ensure the link belongs to the same domain
                if not same_domain(site_search, full_url):
                    continue

                # Check if the link matches the search query
                text = link.get_text(strip=True)
                results.append((full_url, text))

                # Add the link to the queue if not visited
                if full_url not in visited:
                    queue.append(full_url)

        except Exception as e:
            logger.error(f"Error processing {current_url}: {e}")
            queue.pop(0)  # Remove the problematic URL and continue

    # Deduplicate results
    results = list(set(results))
    sorted_urls = sort_urls_by_keyword_similarity(keywords, results)
    return sorted_urls  # Remove duplicates


def same_domain(base_url, href):
    """
    Check if the given URL belongs to the same domain as the base URL.

    Args:
        base_url (str): The base URL.
        href (str): The URL to check.

    Returns:
        bool: True if the URL belongs to the same domain, False otherwise.
    """
    base_host = urlparse(base_url).netloc
    link_host = urlparse(href).netloc

    core_base_host = base_host.removeprefix("www.")
    core_link_host = link_host.removeprefix("www.")

    return core_base_host == core_link_host