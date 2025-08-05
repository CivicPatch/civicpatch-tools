import os
import requests

def search(search_query, site_search=None):
    SERP_API_ENDPOINT = "https://serpapi.com/search"
    api_key = os.getenv("SERP_SEARCH_TOKEN")

    params = {
        "q": search_query,
        "api_key": api_key,
        "engine": "google",  # Specify the search engine (e.g., Google)
    }

    # Add site restriction if provided
    if site_search:
        params["q"] = f"site:{site_search} {search_query}"

    response = requests.get(SERP_API_ENDPOINT, params=params)
    if not response.ok:
        raise Exception(f"SERP API error: {response.status_code} {response.reason}")

    parsed_response = response.json()

    if "organic_results" not in parsed_response:
        return []

    return [
        {"url": result["link"], "text": result["title"]}
        for result in parsed_response["organic_results"]
    ]