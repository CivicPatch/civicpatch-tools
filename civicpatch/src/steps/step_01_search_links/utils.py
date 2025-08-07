from services.google_search import search as google_search
from services.serp_search import search as serp_search
from services.brave_search import search as brave_search 
from utils.array_utils import interleave_arrays
#from utils.log_utils import log_search_engine_call
from utils.config_utils import search_keywords
from utils.data_utils import MunicipalityContext

from src.steps.step_01_search_links.crawl import crawl

SEARCH_SERVICES = {
    "google": google_search,
    "serpapi": serp_search,
    "brave": brave_search,
    "crawl": crawl
}

def search(search_engine: str, municipality_context: MunicipalityContext, search_query: str):
    """
    Perform a search using a specific search engine.
    """
    search_service = SEARCH_SERVICES[search_engine]

    print(f"Searching with {search_engine} for {search_query}")
    keyword_with_type = f"{municipality_context['municipality_entry']['type']} {search_query}"

    results = search_service(
        search_query=keyword_with_type,
        site_search=municipality_context["municipality_entry"]["website"]
    )

    if not results:
        raise Exception(f"No results found with {search_engine}")

    for result in results:
        print(f"-> {result}")
    return results