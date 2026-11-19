from ...schemas import CrawlPageResult, Link, LinkFrontier, LinkStatus, PeopleCollectorContext
from ...utils.links import get_link_status_by_url
from .step_02a_scrape_page.scrape_page import scrape_page
from .step_02b_preprocess_page_content.preprocess_page_content import preprocess_page_content
from .step_02c_process_page_content.process_page_content import process_page_content


async def crawl_page(context: PeopleCollectorContext, page: Link) -> CrawlPageResult:
    preprocessed = context.data.preprocess_page_content_step
    processed = context.data.process_page_content_step

    frontier, final_url = await scrape_page(context, page)
    scraped = _link_with_status(frontier, page.url, LinkStatus.SCRAPED)
    if scraped is None:
        return CrawlPageResult(
            frontier=frontier,
            final_url=final_url,
            preprocess_page_content_step=preprocessed,
            process_page_content_step=processed,
        )

    frontier, preprocessed = preprocess_page_content(_with_frontier(context, frontier), scraped)
    ready = _link_with_status(frontier, page.url, LinkStatus.PREPROCESSED)
    if ready is None:
        return CrawlPageResult(
            frontier=frontier,
            final_url=final_url,
            preprocess_page_content_step=preprocessed,
            process_page_content_step=processed,
        )

    frontier, processed = await process_page_content(_with_frontier(context, frontier), ready)
    return CrawlPageResult(
        frontier=frontier,
        final_url=final_url,
        preprocess_page_content_step=preprocessed,
        process_page_content_step=processed,
    )


def _link_with_status(frontier: LinkFrontier, url: str, status: LinkStatus) -> Link | None:
    # The link as the last step left it: scrape sets the folder_name preprocess reads.
    if get_link_status_by_url(frontier, url) != status:
        return None
    return frontier.get(url)


def _with_frontier(context: PeopleCollectorContext, frontier: LinkFrontier) -> PeopleCollectorContext:
    return context.model_copy(update={"data": context.data.model_copy(update={"frontier": frontier})})
