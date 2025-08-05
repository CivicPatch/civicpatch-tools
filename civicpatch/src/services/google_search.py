import os
import requests

def search(search_query, site_search=None):
    GOOGLE_SEARCH_ENDPOINT = "https://www.googleapis.com/customsearch/v1"
    api_key = os.getenv("GOOGLE_SEARCH_TOKEN")
    search_engine_id = os.getenv("GOOGLE_SEARCH_ENGINE_ID")

    params = {
        "key": api_key,
        "cx": search_engine_id,
        "q": search_query,
    }

    # Add siteSearch and siteSearchFilter if a specific site is provided
    if site_search:
        params["siteSearch"] = site_search
        params["siteSearchFilter"] = "i"  # Include results from the site

    response = requests.get(GOOGLE_SEARCH_ENDPOINT, params=params)
    if not response.ok:
        raise Exception(f"Google Search API error: {response.status_code} {response.reason}")

    parsed_response = response.json()

    if "items" not in parsed_response:
        return []

    return [item["link"] for item in parsed_response["items"]]