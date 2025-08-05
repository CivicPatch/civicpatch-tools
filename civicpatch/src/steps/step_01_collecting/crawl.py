import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

def crawl(search_query, site_search):
    """
    Perform a brute force search using the provided search query and site search.

    Args:
        search_query (str): The query to search for.
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
        current_url = queue.pop(0)
        if current_url in visited:
            continue

        visited.add(current_url)
        try:
            response = requests.get(current_url)
            if response.status_code != 200:
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            for link in soup.find_all("a", href=True):
                href = link["href"]
                full_url = urljoin(current_url, href)

                # Ensure the link belongs to the same domain
                if not same_domain(site_search, full_url):
                    continue

                # Check if the link matches the search query
                if search_query.lower() in link.get_text(strip=True).lower():
                    results.append(full_url)

                # Add the link to the queue if not visited
                if full_url not in visited:
                    queue.append(full_url)

        except Exception as e:
            print(f"Error processing {current_url}: {e}")

    return list(set(results))  # Remove duplicates


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