from jobs.people_collector.schemas import (
  WorkflowStatus,
  PeopleCollectorContext,
  LinkStatus
)

from jobs.people_collector.steps.step_00_prepare_pipeline.prepare_pipeline import prepare_pipeline
from jobs.people_collector.steps.step_01_research_municipality.research_municipality import (
    research_municipality,
)
from jobs.people_collector.steps.step_02_search_links.search_links import search_links
from jobs.people_collector.steps.step_02_search_links.utils import SearchEngineNames
from jobs.people_collector.steps.step_03_scrape_page.scrape_page import scrape_page
from jobs.people_collector.steps.step_04_preprocess_page_content.preprocess_page_content import (
    preprocess_page_content,
)
from jobs.people_collector.steps.step_05_process_page_content.process_page_content import process_page_content
from jobs.people_collector.steps.step_06_merge_records_within_llm.merge_records_within_llm import (
    merge_records_within_llm,
)
from jobs.people_collector.steps.step_07_merge_records_across_llms.merge_records_across_llms import (
    merge_records_across_llms,
)
from jobs.people_collector.steps.step_08_save_output.save_output import save_output
from jobs.people_collector.steps.step_09_cleanup.cleanup import cleanup
from jobs.people_collector.steps.step_10_maybe_send_to_github.maybe_send_to_github import maybe_send_to_github

from jobs.people_collector.transitions.process_page_content_transition import next_state_for_process_content_state
from jobs.people_collector.utils.links import (
    get_next_link_with_status,
    get_link_status_by_url,
    get_links_with_status
)
from shared.schemas import JobConfig
from utils import cost_utils
from utils.log_utils import WorkflowLogger


async def init_transition(job_config: JobConfig, logger: WorkflowLogger, context: PeopleCollectorContext) -> tuple[PeopleCollectorContext, WorkflowStatus]:
    prepare_pipeline(context)
    return context, WorkflowStatus.RESEARCH_MUNICIPALITY

async def research_municipality_transition(job_config: JobConfig, logger: WorkflowLogger, context: PeopleCollectorContext) -> tuple[PeopleCollectorContext, WorkflowStatus]:
    progress, result = research_municipality(context)
    next_state = WorkflowStatus.SEARCH_LINKS

    new_data = context.data.copy(update={
        "progress": progress,
        "research_municipality_step": result
    })

    next_context = context.copy(update={
        "data": new_data
    })

    if next_context.data.config.source_urls and len(next_context.data.config.source_urls) > 0:
        logger.info("Source URLs provided, skipping link search.")
        context.links = [
                Link(url=sl, status=LinkStatus.PENDING.value)
                for sl in next_context.data.config.source_urls
            ]
        next_state = WorkflowStatus.SCRAPE_PAGE
    else:
        logger.info("Source URLs not found, using search engine for links.")
        next_state = WorkflowStatus.SEARCH_LINKS

    return next_context, next_state

async def search_links_transition(_: JobConfig, logger: WorkflowLogger, context: PeopleCollectorContext) -> tuple[PeopleCollectorContext, WorkflowStatus]:
    search_links_step = context.data.search_links_step
    search_link_pointer = search_links_step.search_link_pointer
    next_state = WorkflowStatus.SCRAPE_PAGE
    next_context = context

    if search_link_pointer >= len(SearchEngineNames):
        logger.info("All search engines have been processed.")
        next_state = WorkflowStatus.MERGE_RECORDS_WITHIN_LLM
    else:
        links, result = search_links(context)
        next_context = context.copy(update={
            "data": context.data.copy(update={
                "links": links,
                "search_links_step": result
            })
        })
        next_state = WorkflowStatus.SCRAPE_PAGE

    return next_context, next_state

async def scrape_page_transition(_: JobConfig, logger: WorkflowLogger, context: PeopleCollectorContext) -> tuple[PeopleCollectorContext, WorkflowStatus]:
    page_to_scrape = get_next_link_with_status(context.data.links, LinkStatus.PENDING)
    next_state = WorkflowStatus.PREPROCESS_PAGE_CONTENT

    if not page_to_scrape:
        logger.info("No pending links left to scrape.")
        next_state = WorkflowStatus.MERGE_RECORDS_WITHIN_LLM
        return context, next_state 

    result = await scrape_page(context, page_to_scrape)
    next_context = context.copy(update={
        "data": context.data.copy(update={
            "links": result
        })
    })

    link_status = get_link_status_by_url(context.data.links, page_to_scrape.url)
    if link_status == LinkStatus.SCRAPED:
        next_state = WorkflowStatus.PREPROCESS_PAGE_CONTENT
    else:
        next_state = WorkflowStatus.SCRAPE_PAGE

    return next_context, next_state

async def preprocess_page_content_transition(_: JobConfig, logger: WorkflowLogger, context: PeopleCollectorContext) -> tuple[PeopleCollectorContext, WorkflowStatus]:
    page_to_preprocess = get_next_link_with_status(context.data.links, LinkStatus.SCRAPED)
    next_state = WorkflowStatus.PROCESS_PAGE_CONTENT

    if not page_to_preprocess:
        logger.info("No scraped links left to preprocess.")
        next_state = WorkflowStatus.MERGE_RECORDS_WITHIN_LLM
        return context, next_state

    links, result = preprocess_page_content(context, page_to_preprocess)
    next_context = context.copy(update={
        "data": context.data.copy(update={
            "links": links,
            "preprocess_page_content_step": result
        })
    })

    link_status = get_link_status_by_url(context.data.links, page_to_preprocess.url)

    if link_status == LinkStatus.PREPROCESSED:
        next_state = WorkflowStatus.PROCESS_PAGE_CONTENT
    else:  # link_status == LinkStatus.PREPROCESSED_NO_CONTENT:
        next_state = WorkflowStatus.SCRAPE_PAGE
    return next_context, next_state

async def process_page_content_transition(job_config: JobConfig, logger: WorkflowLogger, context: PeopleCollectorContext) -> tuple[PeopleCollectorContext, WorkflowStatus]:
    preprocessed_links = get_links_with_status(context.data.links, LinkStatus.PREPROCESSED)
    if len(preprocessed_links) == 0:
        # TODO: call legger here
        return context, WorkflowStatus.MERGE_RECORDS_ACROSS_LLMS

    page_to_process = preprocessed_links[0] 
    result = process_page_content(context, page_to_process)
    next_context = context.copy(update={
        "data": context.data.copy(update={
            "progress": result.progress,
            "process_page_content_step": result
        })
    })

    links_processed = get_links_with_status(context.data.links, LinkStatus.DONE)
    current_cost = cost_utils.total_cost_by_request(
        context.request_id, context.data.jurisdiction_id
    )["total_cost"]
    next_state = next_state_for_process_content_state(
        processed_count=len(links_processed),
        current_cost=current_cost,
        job_config=job_config,
        progress=context.data.progress
    )

    return next_context, next_state

async def merge_records_within_llm_transition(_: JobConfig, logger: WorkflowLogger, context: PeopleCollectorContext) -> tuple[PeopleCollectorContext, WorkflowStatus]:
    result = merge_records_within_llm(context)
    next_context = context.copy(update={
        "data": context.data.copy(update={
            "merge_records_within_llm_step": result
        })
    })
    next_state = WorkflowStatus.MERGE_RECORDS_ACROSS_LLMS
    return next_context, next_state

async def merge_records_across_llms_transition(_: JobConfig, logger: WorkflowLogger, context: PeopleCollectorContext) -> tuple[PeopleCollectorContext, WorkflowStatus]:
    result = merge_records_across_llms(context)
    # TODO: save_data to /data file

    next_context = context.copy(update={
        "data": context.data.copy(update={
            "merge_records_across_llms_step": result
        })
    })

    next_state = WorkflowStatus.CLEANUP
    return next_context, next_state

async def cleanup_transition(_: JobConfig, logger: WorkflowLogger, context: PeopleCollectorContext) -> tuple[PeopleCollectorContext, WorkflowStatus]:
    result = cleanup(context)
    next_context = context.copy(update={
        "data": context.data.copy(update={
            "config": context.data.config.copy(update={
                "identities": result["identities"]
            })
        })
    })

    next_state = WorkflowStatus.SAVE_OUTPUT
    return next_context, next_state

async def save_output_transition(_: JobConfig, logger: WorkflowLogger, context: PeopleCollectorContext) -> tuple[PeopleCollectorContext, WorkflowStatus]:
    result = save_output(context)
    next_state = WorkflowStatus.MAYBE_SEND_TO_GITHUB
    return context, next_state

async def maybe_send_to_github_transition(_: JobConfig, logger: WorkflowLogger, context: PeopleCollectorContext) -> tuple[PeopleCollectorContext, WorkflowStatus]:
    cost_utils.log_costs(
        context.request_id, context.data.jurisdiction_id
    )

    result = maybe_send_to_github(context)
    next_state = WorkflowStatus.DONE
    return context, next_state

TRANSITION_MAP = {
  WorkflowStatus.INIT: init_transition,
  WorkflowStatus.RESEARCH_MUNICIPALITY: research_municipality_transition,
  WorkflowStatus.SEARCH_LINKS: search_links_transition,
  WorkflowStatus.SCRAPE_PAGE: scrape_page_transition,
  WorkflowStatus.PREPROCESS_PAGE_CONTENT: preprocess_page_content_transition,
  WorkflowStatus.PROCESS_PAGE_CONTENT: process_page_content_transition,
  WorkflowStatus.MERGE_RECORDS_WITHIN_LLM: merge_records_within_llm_transition,
  WorkflowStatus.MERGE_RECORDS_ACROSS_LLMS: merge_records_across_llms_transition,
  WorkflowStatus.CLEANUP: cleanup_transition,
  WorkflowStatus.SAVE_OUTPUT: save_output_transition,
  WorkflowStatus.MAYBE_SEND_TO_GITHUB: maybe_send_to_github_transition,
}