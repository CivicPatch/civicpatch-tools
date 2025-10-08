from services.google_search import search as google_search
from services.serp_search import search as serp_search
from services.brave_search import search as brave_search 
# from utils.array_utils import interleave_arrays
from utils import cost_utils
# from utils.config_utils import search_keywords

from steps.step_02_search_links.crawl import crawl

# The order here defines the order of search attempts
SEARCH_SERVICES = {
    "google": google_search,
    "serpapi": serp_search,
    "brave": brave_search,
    "crawl": crawl
}

SearchEngineNames = list(SEARCH_SERVICES.keys())

def search(logger, search_engine: str, municipality_name, municipality_website, search_query: str):
    """
    Perform a search using a specific search engine.
    """
    search_service = SEARCH_SERVICES[search_engine]

    logger.info(f"Searching with {search_engine} for {search_query}")
    keyword_with_type = f"{municipality_name} {search_query}"

    results = search_service(
        search_query=keyword_with_type,
        site_search=municipality_website
    )

    if not results:
        raise Exception(f"No results found with {search_engine}")

    for result in results:
        logger.info(f"-> {result}")

    cost_utils.add_search_engine_cost(
        jurisdiction_id=municipality_name,
        search_engine_name=search_engine
    )
    return results