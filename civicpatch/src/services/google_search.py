import os
import requests

def search(search_query, site_search=None):
    GOOGLE_SEARCH_ENDPOINT = "https://www.googleapis.com/customsearch/v1"
    api_key = os.getenv("GOOGLE_SEARCH_TOKEN")
    search_engine_id = os.getenv("GOOGLE_SEARCH_ENGINE_ID")

    if not api_key or not search_engine_id:
        raise ValueError("Google Search API key or search engine ID not set in environment variables.")

    site_query = get_sites_query(site_search) if site_search else ""
    if site_query:
        search_query = f"{search_query} {site_query}"    

    # Add siteSearch and siteSearchFilter if a specific site is provided
    #if site_search:
    #    params["siteSearch"] = site_search
    #    params["siteSearchFilter"] = "i"  # Include results from the site

    params = {
        "key": api_key,
        "cx": search_engine_id,
        "q": f"{search_query} -filetype:pdf'",
    }

    response = requests.get(GOOGLE_SEARCH_ENDPOINT, params=params)
    if not response.ok:
        raise Exception(f"Google Search API error: {response.status_code} {response.reason}")

    parsed_response = response.json()

    if "items" not in parsed_response:
        return []
    
    return [item["link"] for item in parsed_response["items"]]

def get_sites_query(site: str):
    """Generate site query for Google Search, handling both www and non-www versions.
    Args:
        site (str): The base site URL. e.g https://example.com
    Returns:
        str: site:example.com OR site:www.example.com
    """
    site_queries = []
    site_url = site.replace("https://", "").replace("http://", "")
    site_queries.append(f"site:{site_url}")

    if "www." in site_url:
        non_www_site = site_url.replace("www.", "")
        site_queries.append(f"site:{non_www_site}")
    elif not site_url.startswith("www."):
        www_site = "www." + site_url
        site_queries.append(f"site:{www_site}")

    return " OR ".join(site_queries)
