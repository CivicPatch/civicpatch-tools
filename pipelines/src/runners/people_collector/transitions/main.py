from runners.people_collector.schemas import (
  PipelineStatus,
  PeopleCollectorContext,
  Link,
  LinkStatus,
  PeopleCollectorData
)
from shared.utils.statuses import PipelineRunErrorType, PipelineIssueType
from runners.people_collector.steps.step_02_scrape_page.scrape_exceptions import NavigationFailureReason
from shared.utils.url_utils import same_domain, same_url

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

async def start_job(job_config: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, _api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    await prepare_pipeline(context)

    next_context = context.model_copy(update={
        "data": context.data.model_copy(update={
            "links": add_links([], [context.data.config.url]),
        })
    })
    return next_context, PipelineStatus.RESEARCH_MUNICIPALITY

async def research_municipality_transition(job_config: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    result = await research_municipality(context, api_client)
    new_data = context.data.model_copy(update={
        "research_municipality_step": result
    })

    progress = calculate_progress_percentage(context.data, 1)
    next_context = context.model_copy(update={
        "progress": progress,
        "data": new_data
    })

    assert next_context.data.research_municipality_step is not None, "should never happen — research_municipality_step must be set after research_municipality"
    source_urls = next_context.data.research_municipality_step.source_urls
    if source_urls:
        logger.info("Source URLs provided.")
        next_context = next_context.model_copy(update={
            "data": next_context.data.model_copy(update={
                "links": add_links(next_context.data.links, source_urls)
            })
        })

    return next_context, PipelineStatus.SCRAPE_PAGE

def _classify_all_failed_error(links: list) -> PipelineRunErrorType:
    error_links = get_links_with_status(links, [LinkStatus.ERROR])
    if error_links and all(
        l.failure_reason == NavigationFailureReason.NAVIGATION_TIMEOUT for l in error_links
    ):
        return PipelineRunErrorType.DOMAIN_NAVIGATION_TIMEOUT
    return PipelineRunErrorType.DOMAIN_INACTIVE


async def scrape_page_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, _api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    page_to_scrape = get_next_link_with_status(context.data.links, LinkStatus.PENDING)
    next_state = PipelineStatus.PREPROCESS_PAGE_CONTENT

    if not page_to_scrape:
        logger.info("No pending links left to scrape.")
        unprocessable_links = get_links_with_status(context.data.links, [LinkStatus.ERROR, LinkStatus.PREPROCESSED_NO_CONTENT])
        all_failed = bool(context.data.links) and len(unprocessable_links) == len(context.data.links)
        if all_failed:
            if not context.data.find_jurisdiction_url_attempted:
                return context, PipelineStatus.FIND_JURISDICTION_URL
            error_type = _classify_all_failed_error(context.data.links)
            next_context = context.model_copy(update={
                "pipeline_error_type": error_type,
                "data": context.data.model_copy(update={"error_step": error_type}),
            })
            return next_context, PipelineStatus.SEND_ERROR
        next_state = PipelineStatus.MERGE_RECORDS_WITHIN_LLM
        return context, next_state

    links, final_url = await scrape_page(context, page_to_scrape)
    progress = calculate_progress_percentage(context.data, 3)
    next_context = context.model_copy(update={
        "progress": progress,
        "data": context.data.model_copy(update={
            "links": links,
        })
    })

    is_root_link = page_to_scrape.url == context.data.config.url
    if is_root_link and not same_domain(final_url, page_to_scrape.url):
        new_config = context.data.config.model_copy(update={"url": final_url})
        next_context = next_context.model_copy(update={
            "pipeline_issues": next_context.pipeline_issues + [{
                "type": PipelineIssueType.DOMAIN_REDIRECTED,
                "data": {"original_url": page_to_scrape.url, "discovered_url": final_url},
            }],
            "data": next_context.data.model_copy(update={"config": new_config}),
        })

    link_status = get_link_status_by_url(links, final_url)
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
        preprocessed_links = get_links_with_status(context.data.links, [LinkStatus.PREPROCESSED])
        if not preprocessed_links:
            if not context.data.find_jurisdiction_url_attempted:
                return context, PipelineStatus.FIND_JURISDICTION_URL
            error_type = _classify_all_failed_error(context.data.links)
            next_context = context.model_copy(update={
                "pipeline_error_type": error_type,
                "data": context.data.model_copy(update={"error_step": error_type}),
            })
            return next_context, PipelineStatus.SEND_ERROR
        next_state = PipelineStatus.PROCESS_PAGE_CONTENT
        return context, next_state

    links, result = preprocess_page_content(context, page_to_preprocess)
    progress = calculate_progress_percentage(context.data, 4)
    next_context = context.model_copy(update={
        "progress": progress,
        "data": context.data.model_copy(update={
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
        return context, PipelineStatus.MERGE_RECORDS_WITHIN_LLM

    page_to_process = preprocessed_links[0]
    try:
        links, result = await process_page_content(context, page_to_process)
    except Exception as e:
        logger.error(f"process_page_content failed: {e}")
        next_context = context.model_copy(update={
            "data": context.data.model_copy(update={"error_step": str(e)})
        })
        return next_context, PipelineStatus.SEND_ERROR
    progress = calculate_progress_percentage(context.data, 5)
    next_context = context.model_copy(update={
        "progress": progress,
        "data": context.data.model_copy(update={
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
    if stop_warning:
        logger.warning(stop_warning)
    return next_context, next_state

async def merge_records_within_llm_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, _api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    result = merge_records_within_llm(context)
    progress = calculate_progress_percentage(context.data, 6)
    next_context = context.model_copy(update={
        "progress": progress,
        "data": context.data.model_copy(update={
            "merge_records_within_llm_step": result
        })
    })
    return next_context, PipelineStatus.MERGE_RECORDS_ACROSS_LLMS

async def merge_records_across_llms_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, _api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    result = merge_records_across_llms(context)

    progress = calculate_progress_percentage(context.data, 7)
    next_context = context.model_copy(update={
        "progress": progress,
        "data": context.data.model_copy(update={
            "merge_records_across_llms_step": result
        })
    })

    next_state = PipelineStatus.FORMAT_OUTPUT
    return next_context, next_state

async def format_output_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    result = await format_output(context, api_client)
    progress = calculate_progress_percentage(context.data, 8)
    next_context = context.model_copy(update={
        "progress": progress,
        "data": context.data.model_copy(update={
            "format_output_step": result,
        })
    })
    return next_context, PipelineStatus.CLEANUP

async def cleanup_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, _api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    _result = cleanup(context)

    progress = calculate_progress_percentage(context.data, 9)

    next_context = context.model_copy(update={
        "progress": progress
    })
    return next_context, PipelineStatus.REVIEW_OUTPUT

async def review_output_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, _api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    assert context.data.format_output_step is not None
    officials = context.data.format_output_step.officials

    if not officials and not context.data.find_jurisdiction_url_attempted:
        return context, PipelineStatus.FIND_JURISDICTION_URL

    error_type, issues = _collect_pipeline_heuristics(
        officials,
        context.data.role_config,
        context.data.merge_records_within_llm_step,
    )

    if error_type:
        next_context = context.model_copy(update={
            "pipeline_error_type": error_type,
            "data": context.data.model_copy(update={"error_step": error_type}),
        })
        return next_context, PipelineStatus.SEND_ERROR

    result = review_output(context)
    progress = calculate_progress_percentage(context.data, 10)
    next_context = context.model_copy(update={
        "progress": progress,
        "pipeline_issues": issues,
        "data": context.data.model_copy(update={"review_output_step": result}),
    })
    return next_context, PipelineStatus.SAVE_OUTPUT

async def save_output_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, _api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    cost_utils.log_costs(context.request_id, context.data.jurisdiction_ocdid)
    _result = await save_output(context)

    progress = calculate_progress_percentage(context.data, 11)
    next_context = context.model_copy(update={
        "progress": progress
    })

    next_state = PipelineStatus.SEND_SUCCESS
    return next_context, next_state

async def send_success_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    result = await send_success(context, api_client)

    progress = calculate_progress_percentage(context.data, 12)
    next_context = context.model_copy(update={
        "progress": progress,
        "data": context.data.model_copy(update={"send_success_step": result})
    })

    return next_context, PipelineStatus.SUCCESS

async def send_error_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    result = await send_error(context, api_client)

    next_context = context.model_copy(update={
        "data": context.data.model_copy(update={"send_error_step": result})
    })

    return next_context, PipelineStatus.ERROR

async def find_jurisdiction_url_transition(_: JobConfig, logger: PipelineRunLogger, context: PeopleCollectorContext, _api_client: httpx.AsyncClient) -> tuple[PeopleCollectorContext, PipelineStatus]:
    result = await find_jurisdiction_url(context)
    next_context = context.model_copy(update={
        "data": context.data.model_copy(update={
            "find_jurisdiction_url_step": result,
            "find_jurisdiction_url_attempted": True,
        })
    })

    discovered = result.discovered_url
    root_link = next((l for l in context.data.links if l.url == context.data.config.url), None)
    root_failure_reason = root_link.failure_reason if root_link else None

    if root_failure_reason == NavigationFailureReason.NAVIGATION_TIMEOUT and (
        discovered is None or same_domain(discovered, context.data.config.url)
    ):
        return next_context.model_copy(update={
            "pipeline_error_type": PipelineRunErrorType.DOMAIN_NAVIGATION_TIMEOUT,
            "data": next_context.data.model_copy(update={"error_step": PipelineRunErrorType.DOMAIN_NAVIGATION_TIMEOUT}),
        }), PipelineStatus.SEND_ERROR

    if discovered is None:
        return next_context.model_copy(update={
            "pipeline_error_type": PipelineRunErrorType.DOMAIN_INACTIVE,
            "data": next_context.data.model_copy(update={"error_step": PipelineRunErrorType.DOMAIN_INACTIVE}),
        }), PipelineStatus.SEND_ERROR

    if same_domain(discovered, context.data.config.url):
        return next_context, PipelineStatus.REVIEW_OUTPUT

    new_config = context.data.config.model_copy(update={"url": discovered, "source_urls": []})
    return next_context.model_copy(update={
        "pipeline_issues": context.pipeline_issues + [{
            "type": PipelineIssueType.DOMAIN_INACTIVE_FIXED,
            "data": {"original_url": context.data.config.url, "discovered_url": discovered},
        }],
        "data": next_context.data.model_copy(update={
            "config": new_config,
            "links": add_links([], [discovered]),
        }),
    }), PipelineStatus.SCRAPE_PAGE


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