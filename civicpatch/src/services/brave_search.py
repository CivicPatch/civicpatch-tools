import os
import requests
from utils.url_utils import format_url

class BraveSearchError(Exception):
    """Custom exception for Brave Search API errors"""
    pass

def search(search_query, site_search=None):
    token = os.getenv("BRAVE_SEARCH_TOKEN")
    if not token:
        raise BraveSearchError("BRAVE_SEARCH_TOKEN environment variable is not set")

    if site_search:
        search_query += f" site:{site_search}"

    response = requests.get(
        f"https://api.search.brave.com/res/v1/web/search?q={search_query}",
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": os.getenv("BRAVE_SEARCH_TOKEN")
        }
    )
    results_content = response.json()

    if not results_content.get("web"):
        return []

    url_text_pairs = [
        {"url": result["url"], "text": result["title"]}
        for result in results_content["web"].get("results", [])
    ]

    return [format_url(pair["url"]) for pair in url_text_pairs]