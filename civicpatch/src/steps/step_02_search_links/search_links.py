MAX_RETRIES = 3

from utils.scrape_utils import scrape
from schemas import PipelineContext, Link, LinkStatus, PipelineStatus
from utils.array_utils import interleave_arrays
from utils.data_utils import get_municipality_context, MunicipalityContext
from utils.config_utils import search_keywords
from utils.request_utils import with_retry
from .utils import search, SearchEngineNames

def search_links(context: PipelineContext):
    """
    Search for links using multiple search engines and queries.
    """
    print(f"Step 2: {PipelineStatus.SEARCH_LINKS.value}")

    search_link_pointer = context["steps"][PipelineStatus.SEARCH_LINKS.value]["search_link_pointer"]

    # Load keyword term groups
    municipality_context = get_municipality_context(context["state"], context["geoid"])
    government_type = context["steps"][PipelineStatus.RESEARCH_MUNICIPALITY.value]["government_type"]

    keyword_term_groups = search_keywords(government_type)

    urls_found = []

    search_engine = SearchEngineNames[search_link_pointer]

    if not search_engine:
        return {} # TODO set failure

    def search_all_keywords():
        urls_found = []
        for keyword_term in keyword_term_groups:
            print(f"Searching for keyword term: {keyword_term}")
            urls_for_term = municipality_search(municipality_context, search_engine, keyword_term)
            urls_found.append(urls_for_term)
        return urls_found

    try:
        urls_found = with_retry(MAX_RETRIES, search_all_keywords)
        status_value = "completed"
        error_message = None
    except Exception as e:
        urls_found = []
        status_value = "error"
        error_message = str(e)

    interleaved_urls = interleave_arrays(urls_found) if status_value == "completed" else []

    updated_links = context["links"][:]
    for url in interleaved_urls:
        # Do not re-add existing link
        if not any(link["url"] == url for link in context["links"]):
            updated_links.append(Link(url=url, status=LinkStatus.PENDING.value))

    result = {
        "links": [link.model_dump() for link in updated_links],
        "steps": {
            **context["steps"],
            PipelineStatus.SEARCH_LINKS.value: {
                "search_link_pointer": search_link_pointer + 1,
                "search_engines": {
                    **context["steps"][PipelineStatus.SEARCH_LINKS.value]["search_engines"],
                    search_engine: {
                        "links": interleaved_urls,
                        "status": status_value
                    }
                }
            }
        },
    }
    if status_value == "error":
        result["error"] = error_message
    return result

def municipality_search(municipality_context: MunicipalityContext, search_engine, keyword_term: str):
    """
    Search for a single keyword term using multiple search engines with fallback logic.
    """
    query_keywords = keyword_term
    urls = []

    # Construct the search query
    keyword_with_type = f"{municipality_context.municipality_entry.type} {query_keywords}"

    # Perform the search
    results = search(
        search_engine=search_engine,
        municipality_context=municipality_context,
        search_query=keyword_with_type
    )

    if not results:
        raise Exception(f"No results found with {search_engine}")

    print(f"Search successful with {search_engine}. Found {len(results)} results.")
    urls.extend(results)

    return urls  # Return results immediately on success