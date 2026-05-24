import traceback
from runners.people_collector.schemas import (
  PipelineStatus,
  PeopleCollectorContext,
  Link,
  LinkFrontier,
  LinkStatus,
  PeopleCollectorData
)
from shared.utils.statuses import PipelineRunErrorType, PipelineIssueType
from shared.utils.url_utils import canonical_url, same_domain, same_url

from runners.people_collector.steps.step_00_prepare_pipeline.prepare_pipeline import prepare_pipeline
from runners.people_collector.steps.step_01_research_municipality.research_municipality import (
    research_municipality,
)
from runners.people_collector.steps.step_02_scrape_page.scrape_page import scrape_page
from runners.people_collector.steps.step_03_preprocess_page_content.preprocess_page_content import (
    preprocess_page_content,
)
from runners.people_collector.steps.step_04_process_page_content.process_page_content import process_page_content
from runners.people_collector.steps.step_05_merge_records_within_llm.merge_records_within_llm import (
    merge_records_within_llm,
)
from runners.people_collector.steps.step_06_merge_records_across_llms.merge_records_across_llms import (
    merge_records_across_llms,
)
from runners.people_collector.steps.step_07_format_output.format_output import format_output
from runners.people_collector.steps.step_08_cleanup.cleanup import cleanup
from runners.people_collector.steps.step_09_review_output.review_output import review_output
from runners.people_collector.steps.step_10_save_output.save_output import save_output
from runners.people_collector.steps.step_11_send_success.send_success import send_success
from runners.people_collector.steps.step_11_send_error.send_error import send_error
from runners.people_collector.steps.step_09a_find_jurisdiction_url.find_jurisdiction_url import find_jurisdiction_url

from runners.people_collector.transitions.process_page_content_transition import next_process_content_state
from runners.people_collector.utils.links import (
    get_next_link_with_status,
    get_link_status_by_url,
    get_links_with_status,
    add_links,
)

import httpx

from shared.schemas import JobConfig
from utils import cost_utils
from utils.log_utils import PipelineRunLogger


def _next_context(context: PeopleCollectorContext, progress=None, **data_updates) -> PeopleCollectorContext:
    updates = {"data": context.data.model_copy(update=data_updates)} if data_updates else {}
    if progress is not None:
        updates["progress"] = progress
    return context.model_copy(update=updates)


async def start_job(job_config: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, _api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    await prepare_pipeline(context)
    frontier = LinkFrontier.from_urls([context.data.config.url])
    return _next_context(context, frontier=frontier), PipelineStatus.RESEARCH_MUNICIPALITY


async def research_municipality_transition(job_config: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    result = await research_municipality(context, api_client)
    progress = calculate_progress_percentage(context.data, 1)
    next_context = _next_context(context, progress=progress, research_municipality_step=result)

    assert next_context.data.research_municipality_step is not None, "should never happen — research_municipality_step must be set after research_municipality"
    source_urls = next_context.data.research_municipality_step.source_urls
    if source_urls:
        logger.info("Source URLs provided.")
        next_context = _next_context(next_context, frontier=next_context.data.frontier.add(source_urls))

    return next_context, PipelineStatus.SCRAPE_PAGE


def _classify_all_failed_error(frontier: LinkFrontier) -> PipelineRunErrorType:
    error_links = get_links_with_status(frontier, [LinkStatus.ERROR])
    if error_links and all(l.failure_reason is not None for l in error_links):
        return PipelineRunErrorType.DOMAIN_NAVIGATION_ERROR
    return PipelineRunErrorType.DOMAIN_INACTIVE


def _navigation_error_detail(frontier: LinkFrontier) -> dict:
    error_links = get_links_with_status(frontier, [LinkStatus.ERROR])
    if not error_links:
        return {}
    first = error_links[0]
    return {"failure_reason": first.failure_reason, "failure_source": first.failure_source}


async def scrape_page_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, _api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    page_to_scrape = get_next_link_with_status(context.data.frontier, LinkStatus.PENDING)

    if not page_to_scrape:
        logger.info("No pending links left to scrape.")
        unprocessable_links = get_links_with_status(context.data.frontier, [LinkStatus.ERROR, LinkStatus.PREPROCESSED_NO_CONTENT])
        all_failed = bool(context.data.frontier) and len(unprocessable_links) == len(context.data.frontier)
        if all_failed:
            if context.data.find_jurisdiction_url_step is None:
                return context, PipelineStatus.FIND_JURISDICTION_URL
            error_type = _classify_all_failed_error(context.data.frontier)
            detail = _navigation_error_detail(context.data.frontier) if error_type == PipelineRunErrorType.DOMAIN_NAVIGATION_ERROR else None
            return _next_context(context, error_step=error_type, error_detail=detail), PipelineStatus.SEND_ERROR
        return context, PipelineStatus.MERGE_RECORDS_WITHIN_LLM

    frontier, final_url = await scrape_page(context, page_to_scrape)
    progress = calculate_progress_percentage(context.data, 3)
    next_context = _next_context(context, progress=progress, frontier=frontier)

    is_root_link = page_to_scrape.url == context.data.config.url
    if is_root_link and not same_domain(final_url, page_to_scrape.url):
        logger.info(f"Domain redirected: {page_to_scrape.url} -> {final_url}")
        new_config = context.data.config.model_copy(update={"url": final_url})
        next_context = _next_context(next_context, config=new_config)

    link_status = get_link_status_by_url(frontier, page_to_scrape.url)
    next_state = PipelineStatus.PREPROCESS_PAGE_CONTENT if link_status == LinkStatus.SCRAPED else PipelineStatus.SCRAPE_PAGE
    return next_context, next_state


async def preprocess_page_content_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, _api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    page_to_preprocess = get_next_link_with_status(context.data.frontier, LinkStatus.SCRAPED)

    if not page_to_preprocess:
        logger.info("No scraped links left to preprocess.")
        preprocessed_links = get_links_with_status(context.data.frontier, [LinkStatus.PREPROCESSED])
        if not preprocessed_links:
            if context.data.find_jurisdiction_url_step is None:
                return context, PipelineStatus.FIND_JURISDICTION_URL
            error_type = _classify_all_failed_error(context.data.frontier)
            detail = _navigation_error_detail(context.data.frontier) if error_type == PipelineRunErrorType.DOMAIN_NAVIGATION_ERROR else None
            return _next_context(context, error_step=error_type, error_detail=detail), PipelineStatus.SEND_ERROR
        return context, PipelineStatus.PROCESS_PAGE_CONTENT

    frontier, result = preprocess_page_content(context, page_to_preprocess)
    progress = calculate_progress_percentage(context.data, 4)
    next_context = _next_context(context, progress=progress, frontier=frontier, preprocess_page_content_step=result)

    link_status = get_link_status_by_url(frontier, page_to_preprocess.url)
    next_state = PipelineStatus.PROCESS_PAGE_CONTENT if link_status == LinkStatus.PREPROCESSED else PipelineStatus.SCRAPE_PAGE
    return next_context, next_state


async def process_page_content_transition(job_config: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, _api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    preprocessed_links = get_links_with_status(context.data.frontier, [LinkStatus.PREPROCESSED])
    if len(preprocessed_links) == 0:
        return context, PipelineStatus.MERGE_RECORDS_WITHIN_LLM

    page_to_process = preprocessed_links[0]
    try:
        frontier, result = await process_page_content(context, page_to_process)
    except Exception as e:
        logger.error(f"process_page_content failed: {e}")
        return _next_context(context, error_step=str(e)), PipelineStatus.SEND_ERROR

    progress = calculate_progress_percentage(context.data, 5)
    next_context = _next_context(context, progress=progress, frontier=frontier, process_page_content_step=result)

    links_processed = get_links_with_status(next_context.data.frontier, [LinkStatus.PROCESSED_IRRELEVANT, LinkStatus.DONE])
    current_cost = cost_utils.total_cost_by_request(context.request_id, context.data.jurisdiction_ocdid)["total_cost"]
    next_state, stop_warning = next_process_content_state(
        processed_count=len(links_processed),
        current_cost=current_cost,
        job_config=job_config,
        progress=result.progress,
    )
    if stop_warning:
        logger.warning(stop_warning)
    return next_context, next_state


async def merge_records_within_llm_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, _api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    result = merge_records_within_llm(context)
    progress = calculate_progress_percentage(context.data, 6)
    return _next_context(
        context,
        progress=progress,
        merge_records_within_llm_step=result,
    ), PipelineStatus.MERGE_RECORDS_ACROSS_LLMS


async def merge_records_across_llms_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, _api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    result = merge_records_across_llms(context)
    progress = calculate_progress_percentage(context.data, 7)
    return _next_context(
        context,
        progress=progress,
        merge_records_across_llms_step=result,
    ), PipelineStatus.FORMAT_OUTPUT


async def format_output_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    result = await format_output(context, api_client)
    progress = calculate_progress_percentage(context.data, 8)
    return _next_context(
        context,
        progress=progress,
        format_output_step=result,
    ), PipelineStatus.CLEANUP


async def cleanup_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, _api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    _result = cleanup(context)
    progress = calculate_progress_percentage(context.data, 9)
    return _next_context(
        context,
        progress=progress,
    ), PipelineStatus.REVIEW_OUTPUT


async def review_output_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, _api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    assert context.data.format_output_step is not None
    officials = context.data.format_output_step.officials

    if not officials and context.data.find_jurisdiction_url_step is None:
        return context, PipelineStatus.FIND_JURISDICTION_URL

    error_type, issues = _collect_pipeline_heuristics(
        officials,
        context.data.role_config,
        context.data.merge_records_within_llm_step,
    )

    if error_type:
        return _next_context(
            context,
            error_step=error_type,
        ), PipelineStatus.SEND_ERROR

    result = review_output(context)
    progress = calculate_progress_percentage(context.data, 10)
    return _next_context(
        context,
        progress=progress,
        review_output_step=result,
        issues=issues,
    ), PipelineStatus.SAVE_OUTPUT


async def save_output_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, _api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    cost_utils.log_costs(context.request_id, context.data.jurisdiction_ocdid)
    _result = await save_output(context)
    progress = calculate_progress_percentage(context.data, 11)
    return _next_context(
        context,
        progress=progress,
    ), PipelineStatus.SEND_SUCCESS


async def send_success_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    result = await send_success(context, api_client)
    progress = calculate_progress_percentage(context.data, 12)
    return _next_context(
        context,
        progress=progress,
        send_success_step=result,
    ), PipelineStatus.SUCCESS


async def send_error_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    try:
        result = await send_error(context, api_client)
        next_context = _next_context(
            context,
            send_error_step=result,
        )
    except Exception as e:
        logger.error(f"send_error_transition failed: {e}\n{traceback.format_exc()}")
        next_context = context
    return next_context, PipelineStatus.ERROR


async def find_jurisdiction_url_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, _api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    result = await find_jurisdiction_url(context)
    next_context = _next_context(
        context,
        find_jurisdiction_url_step=result,
    )

    discovered = result.discovered_url
    root_link = context.data.frontier.get(context.data.config.url)

    # Navigation failed and search found nothing new — report navigation error
    if root_link is not None and root_link.failure_reason is not None and (
        discovered is None or same_domain(discovered, context.data.config.url)
    ):
        return _next_context(
            next_context,
            error_step=PipelineRunErrorType.DOMAIN_NAVIGATION_ERROR,
            error_detail={"failure_reason": root_link.failure_reason, "failure_source": root_link.failure_source},
        ), PipelineStatus.SEND_ERROR

    # No URL found at all — domain is inactive
    if discovered is None:
        return _next_context(next_context, error_step=PipelineRunErrorType.DOMAIN_INACTIVE), PipelineStatus.SEND_ERROR

    # Found a URL on the same domain — retry review with what we have
    if same_domain(discovered, context.data.config.url):
        return next_context, PipelineStatus.REVIEW_OUTPUT

    # Found a new domain — restart scraping from scratch
    logger.info(f"Inactive domain fixed: {context.data.config.url} -> {discovered}")
    new_config = context.data.config.model_copy(update={"url": discovered, "source_urls": []})
    return _next_context(
        next_context,
        config=new_config,
        frontier=LinkFrontier.from_urls([discovered]),
    ), PipelineStatus.SCRAPE_PAGE


# TODO: steps can go backwards, so progress may decrease at certain points
def calculate_progress_percentage(context_data: PeopleCollectorData, current_step: int):
    total_steps = 13
    if context_data.process_page_content_step is None:
        data_progress = 0
    else:
        data_progress = (context_data.process_page_content_step.progress.current_data \
            / context_data.process_page_content_step.progress.required_data) \
            if context_data.process_page_content_step.progress.required_data > 0 else 0
    steps_progress = (current_step + 1) / total_steps
    combined_progress = data_progress * 0.7 + steps_progress * 0.3
    return int(combined_progress * 100)


def _collect_pipeline_heuristics(officials, role_config, merge_step) -> tuple[str | None, list[dict]]:
    if not officials:
        return PipelineRunErrorType.NO_INFO, []

    issues = []
    for ur in (merge_step.unrecognized_roles if merge_step else []):
        issues.append({"type": PipelineIssueType.UNRECOGNIZED_ROLE, "data": {"role": ur.role, "person_name": ur.person_name}})

    return None, issues


TRANSITION_MAP = {
  PipelineStatus.INIT: start_job,
  PipelineStatus.RESEARCH_MUNICIPALITY: research_municipality_transition,
  PipelineStatus.SCRAPE_PAGE: scrape_page_transition,
  PipelineStatus.PREPROCESS_PAGE_CONTENT: preprocess_page_content_transition,
  PipelineStatus.PROCESS_PAGE_CONTENT: process_page_content_transition,
  PipelineStatus.MERGE_RECORDS_WITHIN_LLM: merge_records_within_llm_transition,
  PipelineStatus.MERGE_RECORDS_ACROSS_LLMS: merge_records_across_llms_transition,
  PipelineStatus.FORMAT_OUTPUT: format_output_transition,
  PipelineStatus.CLEANUP: cleanup_transition,
  PipelineStatus.REVIEW_OUTPUT: review_output_transition,
  PipelineStatus.SAVE_OUTPUT: save_output_transition,
  PipelineStatus.SEND_SUCCESS: send_success_transition,
  PipelineStatus.SEND_ERROR: send_error_transition,
  PipelineStatus.FIND_JURISDICTION_URL: find_jurisdiction_url_transition,
}