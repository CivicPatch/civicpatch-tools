MAX_RETRIES = 3

from typing import Any, Dict, cast

from schemas import (
    Link,
    LinkStatus,
    PipelineContext,
    PipelineStatus,
    ResearchMunicipalityStep,
    SearchEngineState,
    SearchLinksStep,
)
from utils import log_utils
from utils.array_utils import interleave_arrays
from utils.config_utils import search_keywords
from utils.request_utils import with_retry

from .utils import SearchEngineNames, search

DEFAULT_SEARCH_LINKS_STEP = SearchLinksStep(
    search_link_pointer=0,
    search_engines={
        "google": SearchEngineState(links=[], status="not_started"),
        # "serpapi": SearchEngineState(links=[], status="not_started"),
        # "brave": SearchEngineState(links=[], status="not_started"),
        "crawl": SearchEngineState(links=[], status="not_started"),
    },
    error=None,
)


def search_links(context: PipelineContext) -> Dict[str, Any]:
    """
    Search for links using multiple search engines and queries.
    """
    logger = log_utils.get_pipeline_logger(context.jurisdiction_id)
    logger.info(f"Step 2: {PipelineStatus.SEARCH_LINKS.value}")

    search_links_step = context.steps.get(PipelineStatus.SEARCH_LINKS)
    if search_links_step is None:
        search_links_step = DEFAULT_SEARCH_LINKS_STEP
    search_links_step = cast(SearchLinksStep, search_links_step)
    search_link_pointer = search_links_step.search_link_pointer

    # Load keyword term groups
    request_id = context.request_id
    jurisdiction_id = context.jurisdiction_id
    municipality_name = context.name
    municipality_website = context.url

    research_municipality_step = cast(
        ResearchMunicipalityStep, context.steps[PipelineStatus.RESEARCH_MUNICIPALITY]
    )
    government_type = research_municipality_step.government_type

    keyword_term_groups = search_keywords(government_type)

    urls_found = []

    search_engine = SearchEngineNames[search_link_pointer]

    if not search_engine:
        return {}  # TODO set failure

    def search_all_keywords():
        urls_found = []
        for keyword_term in keyword_term_groups:
            logger.info(f"Searching for keyword term: {keyword_term}")
            urls_for_term = municipality_search(
                logger,
                request_id,
                jurisdiction_id,
                municipality_name,
                municipality_website,
                search_engine,
                keyword_term,
            )
            urls_found.append(urls_for_term)
        return urls_found

    try:
        urls_found = with_retry(logger, MAX_RETRIES, search_all_keywords)
        status_value = "completed"
        error_message = None
    except Exception as e:
        urls_found = []
        status_value = "error"
        error_message = str(e)

    interleaved_urls = (
        interleave_arrays(urls_found) if status_value == "completed" else []
    )
    updated_links = context.links.copy()

    for url in interleaved_urls:
        # Do not re-add existing link
        if not any(link.url == url for link in updated_links):
            updated_links.append(Link(url=url, status=LinkStatus.PENDING.value))

    updated_search_engines = {
        **search_links_step.search_engines,
        search_engine: SearchEngineState(links=interleaved_urls, status=status_value),
    }

    result = {
        "links": updated_links,
        "result": SearchLinksStep(
            search_link_pointer=search_link_pointer + 1,
            search_engines=updated_search_engines,
            error=error_message,
        ),
    }

    return result


def municipality_search(
    logger,
    request_id,
    jurisdiction_id,
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
    results = search(
        logger,
        search_engine=search_engine,
        request_id=request_id,
        jurisdiction_id=jurisdiction_id,
        municipality_name=municipality_name,
        municipality_website=municipality_website,
        search_query=keyword_with_type,
    )

    if not results:
        raise Exception(f"No results found with {search_engine}")

    logger.info(
        f"Search successful with {search_engine}. Found {len(results)} results."
    )
    urls.extend(results)

    return urls  # Return results immediately on success
