import time
import traceback

import httpx
from runners.pipeline03_people_collector.constants import MINIMUM_NUM_PEOPLE
from shared.schemas import PipelineRunLimits
from shared.utils.statuses import (
    PipelineIssueType,
    PipelineRunErrorType,
    PipelineRunStatus,
)
from shared.utils.url_utils import same_domain
from utils import cost_utils
from utils.log_utils import PipelineRunLogger

from ..schemas import (
    CrawlPageResult,
    Link,
    LinkFrontier,
    LinkStatus,
    PeopleCollectorContext,
    PeopleCollectorData,
    PeopleCollectorState,
    PeopleCollectorStep,
    ProcessPageContentStep,
    ProgressState,
)
from ..steps.step_00_prepare_pipeline.prepare_pipeline import (
    prepare_pipeline,
)
from ..steps.step_01_research_municipality.research_municipality import (
    research_municipality,
)
from ..steps.step_02_crawl_page.crawl_page import crawl_page
from ..steps.step_03_find_jurisdiction_url.find_jurisdiction_url import (
    find_jurisdiction_url,
)
from ..steps.step_04_cleanup.cleanup import cleanup
from ..steps.step_05_save_output.save_output import save_output
from ..steps.step_06_send_error.send_error import send_error
from ..steps.step_06_send_success.send_success import (
    send_success,
)
from ..transitions.crawl_page_transition import (
    STOP_COST_CAP,
    STOP_MESSAGES,
    describe_progress,
    is_short_of_expected,
    next_crawl_state,
)
from ..utils.links import (
    get_links_with_status,
    get_next_link_with_status,
)


def _next_context(
    context: PeopleCollectorContext, progress=None, **data_updates
) -> PeopleCollectorContext:
    updates = (
        {"data": context.data.model_copy(update=data_updates)} if data_updates else {}
    )
    if progress is not None:
        updates["progress"] = progress
    return context.model_copy(update=updates)


async def start_transition(
    limits: PipelineRunLimits,
    logger: PipelineRunLogger,
    context: PeopleCollectorContext,
    _api_client: httpx.AsyncClient,
) -> tuple[PeopleCollectorContext, PeopleCollectorState]:
    await prepare_pipeline(context)
    frontier = LinkFrontier.from_urls([context.data.config.url])
    return _next_context(
        context, frontier=frontier
    ), PeopleCollectorStep.RESEARCH_MUNICIPALITY


async def research_municipality_transition(
    limits: PipelineRunLimits,
    logger: PipelineRunLogger,
    context: PeopleCollectorContext,
    api_client: httpx.AsyncClient,
) -> tuple[PeopleCollectorContext, PeopleCollectorState]:
    result = await research_municipality(context, api_client)
    progress = calculate_progress_percentage(context.data, 1)
    # The empty process step too: from here on the crawl has progress to read, 0 found of what
    # research expects.
    next_context = _next_context(
        context,
        progress=progress,
        research_municipality_step=result,
        process_page_content_step=ProcessPageContentStep(
            progress=ProgressState(
                required_data=max(MINIMUM_NUM_PEOPLE, len(result.expected_memberships))
            )
        ),
    )

    assert next_context.data.research_municipality_step is not None, (
        "should never happen — research_municipality_step must be set after research_municipality"
    )
    source_urls = next_context.data.research_municipality_step.source_urls
    if source_urls:
        logger.info(f"Source URLs provided: {source_urls}")
        # Ahead of the jurisdiction's homepage, which was seeded before research ran. The
        # homepage stays in the queue behind them, as a fallback for discovering more pages.
        next_context = _next_context(
            next_context, frontier=next_context.data.frontier.add_front(source_urls)
        )

    return next_context, PeopleCollectorStep.CRAWL_PAGE


async def crawl_page_transition(
    limits: PipelineRunLimits,
    logger: PipelineRunLogger,
    context: PeopleCollectorContext,
    _api_client: httpx.AsyncClient,
) -> tuple[PeopleCollectorContext, PeopleCollectorState]:
    page = get_next_link_with_status(context.data.frontier, LinkStatus.PENDING)
    if not page:
        logger.info("No pending links left to crawl.")
        return _next_state_no_pending_pages(context)

    result = await crawl_page(context, page)
    next_context = _context_with_crawl_result(logger, context, page, result)
    return _next_state_after_page(limits, logger, next_context)


def _next_state_no_pending_pages(
    context: PeopleCollectorContext,
) -> tuple[PeopleCollectorContext, PeopleCollectorState]:
    frontier = context.data.frontier
    unusable_links = get_links_with_status(
        frontier, [LinkStatus.ERROR, LinkStatus.PREPROCESSED_NO_CONTENT]
    )
    all_failed = bool(frontier) and len(unusable_links) == len(frontier)
    if not all_failed:
        return context, PeopleCollectorStep.CLEANUP
    if context.data.find_jurisdiction_url_step is None:
        return context, PeopleCollectorStep.FIND_JURISDICTION_URL
    error_type = _all_failed_error_type(frontier)
    detail = (
        _navigation_error_detail(frontier)
        if error_type == PipelineRunErrorType.DOMAIN_NAVIGATION_ERROR
        else None
    )
    return _next_context(
        context, error_step=error_type, error_detail=detail
    ), PipelineRunStatus.SEND_ERROR


def _all_failed_error_type(frontier: LinkFrontier) -> PipelineRunErrorType:
    error_links = get_links_with_status(frontier, [LinkStatus.ERROR])
    if error_links and all(l.failure_reason is not None for l in error_links):
        return PipelineRunErrorType.DOMAIN_NAVIGATION_ERROR
    return PipelineRunErrorType.DOMAIN_INACTIVE


def _navigation_error_detail(frontier: LinkFrontier) -> dict:
    error_links = get_links_with_status(frontier, [LinkStatus.ERROR])
    if not error_links:
        return {}
    first = error_links[0]
    return {
        "failure_reason": first.failure_reason,
        "failure_source": first.failure_source,
    }


def _context_with_crawl_result(
    logger: PipelineRunLogger,
    context: PeopleCollectorContext,
    page: Link,
    result: CrawlPageResult,
) -> PeopleCollectorContext:
    next_context = _next_context(
        context,
        progress=calculate_progress_percentage(context.data, 3),
        frontier=result.frontier,
        preprocess_page_content_step=result.preprocess_page_content_step,
        process_page_content_step=result.process_page_content_step,
    )
    is_root_link = page.url == context.data.config.url
    if is_root_link and not same_domain(result.final_url, page.url):
        logger.info(f"Domain redirected: {page.url} -> {result.final_url}")
        new_config = context.data.config.model_copy(update={"url": result.final_url})
        next_context = _next_context(next_context, config=new_config)
    return next_context


def _next_state_after_page(
    limits: PipelineRunLimits,
    logger: PipelineRunLogger,
    context: PeopleCollectorContext,
) -> tuple[PeopleCollectorContext, PeopleCollectorState]:
    progress = context.data.process_page_content_step.progress
    processed_count = len(
        get_links_with_status(
            context.data.frontier, [LinkStatus.PROCESSED_IRRELEVANT, LinkStatus.DONE]
        )
    )
    current_cost = cost_utils.total_cost(context.pipeline_run_id)
    elapsed_seconds = time.time() - context.created_at
    logger.info(
        describe_progress(
            processed_count, current_cost, limits, progress, elapsed_seconds
        )
    )
    next_state, stop_reason = next_crawl_state(
        processed_count, current_cost, limits, progress, elapsed_seconds
    )
    # Carried on the context, not just logged: `review_output_transition` turns a cost-cap
    # stop into an issue the reviewer sees.
    if stop_reason:
        logger.warning(STOP_MESSAGES[stop_reason])
    return _next_context(context, stop_reason=stop_reason), next_state


async def cleanup_transition(
    _: PipelineRunLimits,
    logger: PipelineRunLogger,
    context: PeopleCollectorContext,
    _api_client: httpx.AsyncClient,
) -> tuple[PeopleCollectorContext, PeopleCollectorState]:
    _result = cleanup(context)
    progress = calculate_progress_percentage(context.data, 9)
    return _next_context(
        context,
        progress=progress,
    ), PeopleCollectorStep.REVIEW_OUTPUT


async def review_output_transition(
    _: PipelineRunLimits,
    logger: PipelineRunLogger,
    context: PeopleCollectorContext,
    _api_client: httpx.AsyncClient,
) -> tuple[PeopleCollectorContext, PeopleCollectorState]:
    records = context.data.process_page_content_step.all_records()

    if not records and context.data.find_jurisdiction_url_step is None:
        return context, PeopleCollectorStep.FIND_JURISDICTION_URL

    error_type, issues = _collect_pipeline_heuristics(
        records,
        context.data.stop_reason,
        context.data.process_page_content_step.progress,
    )

    if error_type:
        return _next_context(
            context,
            error_step=error_type,
        ), PipelineRunStatus.SEND_ERROR

    progress = calculate_progress_percentage(context.data, 10)
    return _next_context(
        context,
        progress=progress,
        issues=issues,
    ), PeopleCollectorStep.SAVE_OUTPUT


async def save_output_transition(
    _: PipelineRunLimits,
    logger: PipelineRunLogger,
    context: PeopleCollectorContext,
    _api_client: httpx.AsyncClient,
) -> tuple[PeopleCollectorContext, PeopleCollectorState]:
    cost_utils.log_costs(context.pipeline_run_id, context.data.jurisdiction_ocdid)
    _result = await save_output(context)
    progress = calculate_progress_percentage(context.data, 11)
    return _next_context(
        context,
        progress=progress,
    ), PeopleCollectorStep.SEND_SUCCESS


async def send_success_transition(
    _: PipelineRunLimits,
    logger: PipelineRunLogger,
    context: PeopleCollectorContext,
    api_client: httpx.AsyncClient,
) -> tuple[PeopleCollectorContext, PeopleCollectorState]:
    result = await send_success(context, api_client)
    progress = calculate_progress_percentage(context.data, 12)
    return _next_context(
        context,
        progress=progress,
        send_success_step=result,
    ), PipelineRunStatus.SUCCESS


async def send_error_transition(
    _: PipelineRunLimits,
    logger: PipelineRunLogger,
    context: PeopleCollectorContext,
    api_client: httpx.AsyncClient,
) -> tuple[PeopleCollectorContext, PeopleCollectorState]:
    # A run that failed still spent money — 24 of 49 dismissed scrapes on dev wrote no
    # costs.json at all. Before `send_error`, which zips the artifacts this belongs in.
    # Recoverable on its own: an unreported cost must not cost us the error report.
    try:
        cost_utils.log_costs(context.pipeline_run_id, context.data.jurisdiction_ocdid)
    except Exception as e:
        logger.error(f"Failed to write costs for a failed run: {e}")

    try:
        result = await send_error(context, api_client)
        next_context = _next_context(
            context,
            send_error_step=result,
        )
    except Exception as e:
        logger.error(f"send_error_transition failed: {e}\n{traceback.format_exc()}")
        next_context = context
    return next_context, PipelineRunStatus.ERROR


async def find_jurisdiction_url_transition(
    _: PipelineRunLimits,
    logger: PipelineRunLogger,
    context: PeopleCollectorContext,
    _api_client: httpx.AsyncClient,
) -> tuple[PeopleCollectorContext, PeopleCollectorState]:
    result = await find_jurisdiction_url(context)
    next_context = _next_context(
        context,
        find_jurisdiction_url_step=result,
    )

    discovered = result.discovered_url
    root_link = context.data.frontier.get(context.data.config.url)

    # Navigation failed and search found nothing new — report navigation error
    if (
        root_link is not None
        and root_link.failure_reason is not None
        and (discovered is None or same_domain(discovered, context.data.config.url))
    ):
        return _next_context(
            next_context,
            error_step=PipelineRunErrorType.DOMAIN_NAVIGATION_ERROR,
            error_detail={
                "failure_reason": root_link.failure_reason,
                "failure_source": root_link.failure_source,
            },
        ), PipelineRunStatus.SEND_ERROR

    # No URL found at all — domain is inactive
    if discovered is None:
        return _next_context(
            next_context, error_step=PipelineRunErrorType.DOMAIN_INACTIVE
        ), PipelineRunStatus.SEND_ERROR

    # Found a URL on the same domain — retry review with what we have
    if same_domain(discovered, context.data.config.url):
        return next_context, PeopleCollectorStep.REVIEW_OUTPUT

    # Found a new domain — restart scraping from scratch
    logger.info(f"Inactive domain fixed: {context.data.config.url} -> {discovered}")
    new_config = context.data.config.model_copy(
        update={"url": discovered, "source_urls": []}
    )
    return _next_context(
        next_context,
        config=new_config,
        frontier=LinkFrontier.from_urls([discovered]),
    ), PeopleCollectorStep.CRAWL_PAGE


# TODO: steps can go backwards, so progress may decrease at certain points
def calculate_progress_percentage(context_data: PeopleCollectorData, current_step: int):
    total_steps = 11
    progress = context_data.process_page_content_step.progress
    # Finding more people than expected is still a complete roster, not more than complete.
    data_progress = (
        min(1, progress.current_data / progress.required_data)
        if progress.required_data > 0
        else 0
    )
    steps_progress = (current_step + 1) / total_steps
    combined_progress = data_progress * 0.7 + steps_progress * 0.3
    return int(combined_progress * 100)


def _collect_pipeline_heuristics(
    records, stop_reason: str | None = None, progress: ProgressState | None = None
) -> tuple[str | None, list[dict]]:
    """Emptiness, a crawl that stopped at its ceiling, and one that ran out of pages short of
    the roster it expected. An unrecognized role is not an issue here: the raw label crosses
    the boundary in the record, so `parse_label` recovers `unmatched` wherever it is needed.

    Ordered, and only one is returned: a run that found nothing has nothing partial to warn
    about, and a run that stopped at its cost cap has already said why it is short. Reporting
    two would put one run's single fact on the issues page twice.
    """
    if not records:
        return PipelineRunErrorType.NO_ROSTER_FOUND, []
    if stop_reason == STOP_COST_CAP:
        return None, [{"type": PipelineIssueType.COST_CAP_REACHED, "data": {}}]
    if progress and is_short_of_expected(progress):
        return None, [
            {
                "type": PipelineIssueType.FEWER_THAN_EXPECTED,
                "data": {
                    "found": progress.current_data,
                    "expected": progress.required_data,
                },
            }
        ]
    return None, []


TRANSITION_MAP = {
    PipelineRunStatus.INIT: start_transition,
    PeopleCollectorStep.RESEARCH_MUNICIPALITY: research_municipality_transition,
    PeopleCollectorStep.CRAWL_PAGE: crawl_page_transition,
    PeopleCollectorStep.CLEANUP: cleanup_transition,
    PeopleCollectorStep.REVIEW_OUTPUT: review_output_transition,
    PeopleCollectorStep.SAVE_OUTPUT: save_output_transition,
    PeopleCollectorStep.SEND_SUCCESS: send_success_transition,
    PipelineRunStatus.SEND_ERROR: send_error_transition,
    PeopleCollectorStep.FIND_JURISDICTION_URL: find_jurisdiction_url_transition,
}
