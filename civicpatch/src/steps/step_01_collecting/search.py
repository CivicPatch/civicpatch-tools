from services.google_search import search as google_search
from services.serp_search import search as serp_search
from services.brave_search import search as brave_search 
from . import crawl
from utils.array_utils import interleave_arrays
#from utils.log_utils import log_search_engine_call
from utils.data_utils import get_municipality_context

SEARCH_SERVICES = {
    "google": google_search,
    "serpapi": serp_search,
    "brave": brave_search,
    "crawl": crawl
}

def get_candidate_urls(state, geoid):
    keyword_term_groups = []
    municipality_context = get_municipality_context(state, geoid)

    urls_by_keywords = [
        search(municipality_context, keyword_term_group)
        for keyword_term_group in keyword_term_groups
    ]

    # Interleave the URLs by keywords and remove duplicates
    return list(set(interleave_arrays(urls_by_keywords)))

def search(municipality_context, keyword_term_group):
    query_keywords = keyword_term_group["name"]

    for search_engine_name, search_service in SEARCH_SERVICES.items():
        try:
            keyword_with_type = f"{municipality_context['type']} {query_keywords}"
            print(f"Searching with {search_engine_name} for {keyword_with_type}")

            results = search_service(
                search_query=keyword_with_type,
                site_search=municipality_context.get("website")
            )

            #if search_engine_name != "crawl":
            #    log_search_engine_call(
            #        municipality_context["state"],
            #        municipality_context["name"],
            #        search_engine_name
            #    )

            if not results:
                raise Exception(f"No results found with {search_engine_name}")

            print(f"Search successful with {search_engine_name}.")
            return results  # Return results immediately on success

        except Exception as e:
            print(f"Error with {search_engine_name}: {e}. Trying next service...")
            continue

    print(f"Error: All search services failed for municipality: {municipality_context}")
    return []