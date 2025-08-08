from utils.scrape_utils import scrape
from schemas import PipelineContext, Link, LinkStatus, PipelineStatus
from utils.array_utils import interleave_arrays
from utils.data_utils import get_municipality_context, MunicipalityContext
from utils.config_utils import search_keywords
from .utils import search, SEARCH_SERVICES

def search_links(context: PipelineContext):
    """
    Search for links using multiple search engines and queries.
    """
    print(f"Step 2: {PipelineStatus.SEARCH_LINKS.value}")

    # Load keyword term groups
    municipality_context = get_municipality_context(context["state"], context["geoid"])
    government_type = context["steps"][PipelineStatus.RESEARCH_MUNICIPALITY.value]["government_type"]

    keyword_term_groups = search_keywords(government_type)

    all_urls = []

    search_engine = None
    for search_engine_name in SEARCH_SERVICES.keys():
        if context["search_engines"][search_engine_name]["status"] == "not_started":
            search_engine = search_engine_name
            break

    # TODO: implement
    
    if not search_engine:
        return {
            "search_engines": {} # Set failure
        }

    for keyword_term in keyword_term_groups:
        print(f"Searching for keyword term: {keyword_term}")
        urls_for_term = municipality_search(municipality_context, search_engine, keyword_term)
        all_urls.append(urls_for_term)

    interleaved_urls = interleave_arrays(all_urls)

    updated_links = context["links"][:]
    for url in interleaved_urls:
        # Do not re-add existing link
        if not any(link["url"] == url for link in context["links"]):
            updated_links.append(Link(url=url, status=LinkStatus.PENDING.value))


    return {
        "links": updated_links,
        "search_engines": {
            **context["search_engines"],
            search_engine: {
                "links": interleaved_urls,
                "status": "processing"
            }
        }
    }

def municipality_search(municipality_context: MunicipalityContext, search_engine, keyword_term: str):
    """
    Search for a single keyword term using multiple search engines with fallback logic.
    """
    query_keywords = keyword_term
    urls = []

    # Construct the search query
    keyword_with_type = f"{municipality_context['municipality_entry']['type']} {query_keywords}"

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