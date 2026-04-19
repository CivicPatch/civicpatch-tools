from runners.people_collector.schemas import (
  PipelineStatus,
  PeopleCollectorContext,
  Link,
  LinkStatus,
  PeopleCollectorData
)
from shared.utils.statuses import PipelineRunErrorType, PipelineIssueType

from runners.people_collector.steps.step_00_prepare_pipeline.prepare_pipeline import prepare_pipeline
from runners.people_collector.steps.step_01_research_municipality.research_municipality import (
    research_municipality,
)
from runners.people_collector.steps.step_02_search_links.search_links import search_links
from runners.people_collector.steps.step_02_search_links.search_links import SearchEngineNames
from runners.people_collector.steps.step_03_scrape_page.scrape_page import scrape_page
from runners.people_collector.steps.step_04_preprocess_page_content.preprocess_page_content import (
    preprocess_page_content,
)
from runners.people_collector.steps.step_05_process_page_content.process_page_content import process_page_content
from runners.people_collector.steps.step_06_merge_records_within_llm.merge_records_within_llm import (
    merge_records_within_llm,
)
from runners.people_collector.steps.step_07_merge_records_across_llms.merge_records_across_llms import (
    merge_records_across_llms,
)
from runners.people_collector.steps.step_08_format_output.format_output import format_output
from runners.people_collector.steps.step_09_cleanup.cleanup import cleanup
from runners.people_collector.steps.step_10_review_output.review_output import review_output
from runners.people_collector.steps.step_10_save_output.save_output import save_output
from runners.people_collector.steps.step_11_send_success.send_success import send_success
from runners.people_collector.steps.step_11_send_error.send_error import send_error

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

async def start_job(job_config: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, _api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    await prepare_pipeline(context)

    next_context = context.copy(update={
        "data": context.data.copy(update={
            "links": add_links([], [context.data.config.url]),
        })
    })
    return next_context, PipelineStatus.RESEARCH_MUNICIPALITY

async def research_municipality_transition(job_config: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    result = await research_municipality(context, api_client)
    next_state = PipelineStatus.SEARCH_LINKS

    new_data = context.data.copy(update={
        "research_municipality_step": result
    })

    progress = calculate_progress_percentage(context.data, 1)
    next_context = context.copy(update={
        "progress": progress,
        "data": new_data
    })

    assert next_context.data.research_municipality_step is not None, "should never happen — research_municipality_step must be set after research_municipality"
    source_urls = next_context.data.research_municipality_step.source_urls
    if source_urls:
        logger.info("Source URLs provided, skipping link search.")
        next_context = next_context.copy(update={
            "data": next_context.data.copy(update={
                "links": add_links(next_context.data.links, source_urls)
            })
        })

        next_state = PipelineStatus.SCRAPE_PAGE
    else:
        logger.info("Source URLs not found, using search engine for links.")
        next_state = PipelineStatus.SEARCH_LINKS

    
    return next_context, next_state

async def search_links_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, _api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    search_links_step = context.data.search_links_step
    search_link_pointer = search_links_step.search_link_pointer
    next_state = PipelineStatus.SCRAPE_PAGE
    next_context = context

    if search_link_pointer >= len(SearchEngineNames):
        logger.info("All search engines have been processed.")

        next_state = PipelineStatus.SCRAPE_PAGE
    else:
        links, result = await search_links(context)
        progress = calculate_progress_percentage(context.data, 2)
        next_context = context.copy(update={
            "progress": progress,
            "data": context.data.copy(update={
                "links": links,
                "search_links_step": result
            })
        })
        if len(links) == 0:
            logger.info("No links found, re-running step to try next search engine.")
            next_state = PipelineStatus.SEARCH_LINKS
        else:
            next_state = PipelineStatus.SCRAPE_PAGE

    
    return next_context, next_state

async def scrape_page_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, _api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    page_to_scrape = get_next_link_with_status(context.data.links, LinkStatus.PENDING)
    next_state = PipelineStatus.PREPROCESS_PAGE_CONTENT

    if not page_to_scrape:
        logger.info("No pending links left to scrape.")
        next_state = PipelineStatus.MERGE_RECORDS_WITHIN_LLM
        return context, next_state

    links = await scrape_page(context, page_to_scrape)
    progress = calculate_progress_percentage(context.data, 3)
    next_context = context.copy(update={
        "progress": progress,
        "data": context.data.copy(update={
            "links": links,
        })
    })

    link_status = get_link_status_by_url(context.data.links, page_to_scrape.url)
    if link_status == LinkStatus.SCRAPED:
        next_state = PipelineStatus.PREPROCESS_PAGE_CONTENT
    else:
        next_state = PipelineStatus.SCRAPE_PAGE

    
    return next_context, next_state

async def preprocess_page_content_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, _api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    page_to_preprocess = get_next_link_with_status(context.data.links, LinkStatus.SCRAPED)
    next_state = PipelineStatus.PROCESS_PAGE_CONTENT

    if not page_to_preprocess:
        logger.info("No scraped links left to preprocess.")
        next_state = PipelineStatus.MERGE_RECORDS_WITHIN_LLM
        return context, next_state

    links, result = preprocess_page_content(context, page_to_preprocess)
    progress = calculate_progress_percentage(context.data, 4)
    next_context = context.copy(update={
        "progress": progress,
        "data": context.data.copy(update={
            "links": links,
            "preprocess_page_content_step": result
        })
    })

    link_status = get_link_status_by_url(context.data.links, page_to_preprocess.url)

    if link_status == LinkStatus.PREPROCESSED:
        next_state = PipelineStatus.PROCESS_PAGE_CONTENT
    else:  # link_status == LinkStatus.PREPROCESSED_NO_CONTENT:
        next_state = PipelineStatus.SCRAPE_PAGE
    
    
    return next_context, next_state

async def process_page_content_transition(job_config: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, _api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    preprocessed_links = get_links_with_status(context.data.links, [LinkStatus.PREPROCESSED])
    if len(preprocessed_links) == 0:
        error_links = get_links_with_status(context.data.links, [LinkStatus.ERROR])
        if context.data.links and len(error_links) == len(context.data.links):
            next_context = context.copy(update={
                "data": context.data.copy(update={"error_step": "All pages were unreachable"})
            })
            return next_context, PipelineStatus.SEND_ERROR
        return context, PipelineStatus.MERGE_RECORDS_ACROSS_LLMS

    page_to_process = preprocessed_links[0]
    try:
        links, result = await process_page_content(context, page_to_process)
    except Exception as e:
        logger.error(f"process_page_content failed: {e}")
        next_context = context.copy(update={
            "data": context.data.copy(update={"error_step": str(e)})
        })
        return next_context, PipelineStatus.SEND_ERROR
    progress = calculate_progress_percentage(context.data, 5)
    next_context = context.copy(update={
        "progress": progress,
        "data": context.data.copy(update={
            "links": links,
            "process_page_content_step": result
        },
        )
    })

    links_processed = get_links_with_status(next_context.data.links, [LinkStatus.PROCESSED_IRRELEVANT, LinkStatus.DONE])
    current_cost = cost_utils.total_cost_by_request(
        context.request_id, context.data.jurisdiction_ocdid
    )["total_cost"]
    next_state, stop_warning = next_process_content_state(
        processed_count=len(links_processed),
        current_cost=current_cost,
        job_config=job_config,
        progress=result.progress,
    )
    if stop_warning and next_state == PipelineStatus.SEND_ERROR:
        next_context = next_context.copy(update={
            "data": next_context.data.copy(update={"error_step": stop_warning})
        })
    elif stop_warning:
        logger.warning(stop_warning)
    return next_context, next_state

async def merge_records_within_llm_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, _api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    result = merge_records_within_llm(context)
    progress = calculate_progress_percentage(context.data, 6)
    next_context = context.copy(update={
        "progress": progress,
        "data": context.data.copy(update={
            "merge_records_within_llm_step": result
        })
    })
    return next_context, PipelineStatus.MERGE_RECORDS_ACROSS_LLMS

async def merge_records_across_llms_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, _api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    result = merge_records_across_llms(context)

    progress = calculate_progress_percentage(context.data, 7)
    next_context = context.copy(update={
        "progress": progress,
        "data": context.data.copy(update={
            "merge_records_across_llms_step": result
        })
    })

    next_state = PipelineStatus.FORMAT_OUTPUT
    return next_context, next_state

async def format_output_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    result = await format_output(context, api_client)
    progress = calculate_progress_percentage(context.data, 8)
    next_context = context.copy(update={
        "progress": progress,
        "data": context.data.copy(update={
            "format_output_step": result,
        })
    })
    return next_context, PipelineStatus.CLEANUP

async def cleanup_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, _api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    _result = cleanup(context)

    progress = calculate_progress_percentage(context.data, 9)

    next_context = context.copy(update={
        "progress": progress
    })
    return next_context, PipelineStatus.REVIEW_OUTPUT

async def review_output_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, _api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    assert context.data.format_output_step is not None
    officials = context.data.format_output_step.officials
    error_type, issues = _collect_pipeline_heuristics(
        officials,
        context.data.role_config,
        context.data.merge_records_within_llm_step,
    )

    if error_type:
        next_context = context.copy(update={
            "pipeline_error_type": error_type,
            "data": context.data.copy(update={"error_step": error_type}),
        })
        return next_context, PipelineStatus.SEND_ERROR

    result = review_output(context)
    progress = calculate_progress_percentage(context.data, 10)
    next_context = context.copy(update={
        "progress": progress,
        "pipeline_issues": issues,
        "data": context.data.copy(update={"review_output_step": result}),
    })
    return next_context, PipelineStatus.SAVE_OUTPUT

async def save_output_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, _api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    cost_utils.log_costs(context.request_id, context.data.jurisdiction_ocdid)
    _result = await save_output(context)

    progress = calculate_progress_percentage(context.data, 11)
    next_context = context.copy(update={
        "progress": progress
    })

    next_state = PipelineStatus.SEND_SUCCESS
    return next_context, next_state

async def send_success_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    result = await send_success(context, api_client)

    progress = calculate_progress_percentage(context.data, 12)
    next_context = context.copy(update={
        "progress": progress,
        "data": context.data.copy(update={"send_success_step": result})
    })

    return next_context, PipelineStatus.SUCCESS

async def send_error_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    result = await send_error(context, api_client)

    next_context = context.copy(update={
        "data": context.data.copy(update={"send_error_step": result})
    })

    return next_context, PipelineStatus.ERROR

# TODO: issue with this is that steps can go backwards, so progress
# might decrease at certain points. Should fix.
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
    progress_percent = int(combined_progress * 100)
    return progress_percent

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
  PipelineStatus.SEARCH_LINKS: search_links_transition,
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
}