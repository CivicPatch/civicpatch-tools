from typing import Any, Dict, cast, List

from jobs.people_collector.schemas import (
    Link,
    LinkStatus,
    PeopleCollectorContext,
    WorkflowStatus,
    SearchEngineState,
    SearchLinksStep,
)
from shared.utils.config_utils import search_keywords, crawl_keywords
from utils import log_utils
from utils.array_utils import interleave_arrays
from utils.request_utils import with_retry

from services.google_search import search as google_search
from services.serp_search import search as serp_search
from services.brave_search import search as brave_search 
from utils import cost_utils

from jobs.people_collector.steps.step_02_search_links.crawl import crawl

MAX_RETRIES = 3
# The order here defines the order of search attempts
SEARCH_SERVICES = {
    "google": google_search,
    #"serpapi": serp_search,
    #"brave": brave_search,
    "crawl": crawl
}

SearchEngineNames = list(SEARCH_SERVICES.keys())

# TODO: Half-written with AI, half edited by myself this is so ugly it needs to die in a fire
# TBD please fix

async def search_links(context: PeopleCollectorContext) -> tuple[List[Link], SearchLinksStep]:
    """
    Search for links using multiple search engines and queries.
    """
    logger = log_utils.get_workflow_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step 2: {WorkflowStatus.SEARCH_LINKS.value} from website: {context.data.config.url}")

    search_links_step = context.data.search_links_step
    search_link_pointer = search_links_step.search_link_pointer

    # Load keyword term groups
    request_id = context.request_id
    jurisdiction_ocdid = context.data.jurisdiction_ocdid
    municipality_name = context.data.config.name
    municipality_website = context.data.config.url

    search_keys = search_keywords("local")
    crawl_keys = crawl_keywords("local")

    urls_found = []

    search_engine = SearchEngineNames[search_link_pointer]

    async def search_all_keywords():
        urls_found = []

        if search_engine == "crawl":
            crawl_urls = await crawl(logger, crawl_keys, municipality_website)
            urls_found = [crawl_urls]
        else:
            for keyword_term in search_keys:
                logger.info(f"Searching for keyword term: {keyword_term}",)
                urls_for_term = await municipality_search(
                    logger,
                    request_id,
                    jurisdiction_ocdid,
                    municipality_name,
                    municipality_website,
                    search_engine,
                    keyword_term,
                )
                urls_found.append(urls_for_term)
        return urls_found

    try:
        urls_found = await search_all_keywords()
        status_value = "completed"
        error_message = None
    except Exception as e:
        urls_found = []
        status_value = "error"
        error_message = str(e)

    interleaved_urls = (
        interleave_arrays(urls_found) if status_value == "completed" else []
    )
    updated_links = context.data.links.copy()

    for url in interleaved_urls:
        # Do not re-add existing link
        if not any(link.url == url for link in updated_links):
            updated_links.append(Link(url=url, status=LinkStatus.PENDING.value))

    updated_search_engines = {
        **search_links_step.search_engines,
        search_engine: SearchEngineState(links=interleaved_urls, status=status_value),
    }

    if error_message:
        logger.error(f"Error during search with {search_engine}: {error_message}")

    return updated_links, SearchLinksStep(
        search_link_pointer=search_link_pointer + 1,
        search_engines=updated_search_engines,
        error=error_message,
    ),

async def municipality_search(
    logger,
    request_id,
    jurisdiction_ocdid,
    municipality_name,
    municipality_website,
    search_engine,
    keyword_term: str,
):
    """
    Search for a single keyword term using multiple search engines with fallback logic.
    """
    query_keywords = keyword_term
    urls = []

    # Construct the search query
    keyword_with_type = f"{municipality_name} {query_keywords}"

    # Perform the search
    results = await search(
        logger,
        search_engine=search_engine,
        request_id=request_id,
        jurisdiction_ocdid=jurisdiction_ocdid,
        municipality_name=municipality_name,
        municipality_website=municipality_website,
        search_query=keyword_with_type,
    )

    if not results:
        logger.error(f"No results found with {search_engine}")
        raise Exception(f"No results found with {search_engine}")

    logger.info(
        f"Search successful with {search_engine}. Found {len(results)} results."
    )
    urls.extend(results)

    return urls  # Return results immediately on success

async def search(logger, search_engine: str, request_id, jurisdiction_ocdid, municipality_name, municipality_website, search_query: str):
    """
    Perform a search using a specific search engine.
    """
    search_service = SEARCH_SERVICES[search_engine]

    logger.info(f"Searching with {search_engine} for {search_query}")
    keyword_with_type = f"{municipality_name} {search_query}"

    results = await search_service(
        logger,
        search_query=keyword_with_type,
        site_search=municipality_website
    )

    if not results:
        raise Exception(f"No results found with {search_engine}")

    results_without_pdfs = [url for url in results if not ".pdf" in url.lower()]
    results = results_without_pdfs

    for result in results:
        logger.info(f"-> {result}")

    cost_utils.add_search_engine_cost(
        request_id=request_id,
        jurisdiction_ocdid=jurisdiction_ocdid,
        search_engine_name=search_engine
    )
    return results