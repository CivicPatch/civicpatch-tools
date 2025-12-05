from typing import List, cast
from schemas import (
  Link, LinkStatus, ProgressState,
  ProcessPageContentStep
)
from jobs.people_collector.schemas import PipelineStatus
from shared.schemas import ProcessConfig
from decimal import Decimal
from steps.step_05_process_page_content.process_page_content import process_page_content

def handle_process_page_content_state(logger, 
                                      process_config: ProcessConfig,
                                      context: PipelineContext,
                                      current_cost: Decimal):
  preprocessed_links = get_links_with_status(context.links, LinkStatus.PREPROCESSED)
  links_processed = get_links_with_status(context.links, LinkStatus.DONE)
  processed_count = len(links_processed)

  if len(preprocessed_links) == 0:
      logger.info("No preprocessed links left to process.")
      return {}, PipelineStatus.MERGE_RECORDS_ACROSS_LLMS

  page_to_process = preprocessed_links[0]

  step_result = process_page_content(context, page_to_process)
  next_state = determine_next_state_for_process_content_state(
    processed_count, 
    current_cost,
    process_config,
    context.progress
  )
  return step_result, next_state

def determine_next_state_for_process_content_state(
    processed_count: int,
    current_cost: Decimal,
    process_config: ProcessConfig,
    progress: ProgressState
) -> PipelineStatus:
    if should_stop_for_cost_limit(current_cost, process_config):
        return PipelineStatus.MERGE_RECORDS_WITHIN_LLM
    
    if should_stop_for_data_requirement(progress):
        return PipelineStatus.MERGE_RECORDS_WITHIN_LLM
    
    if should_stop_for_max_pages(processed_count, process_config, progress):
        return PipelineStatus.MERGE_RECORDS_WITHIN_LLM
    
    return PipelineStatus.SCRAPE_PAGE

def get_next_link_with_status(links: List[Link], status: LinkStatus) -> Link | None:
    for link in links:
        if link.status == status.value:
            return link
    return None

def get_link_status_by_url(links: List[Link], url: str) -> LinkStatus | None:
    for link in links:
        if link.url == url:
            return LinkStatus(link.status)
    return None

def get_links_with_status(links: List[Link], status: LinkStatus) -> List[Link]:
    return [link for link in links if link.status == status.value]

def should_stop_for_cost_limit(current_cost: Decimal, process_config: ProcessConfig) -> bool:
    return current_cost >= process_config.pipeline_run_cost_limit

def should_stop_for_data_requirement(progress: ProgressState) -> bool:
    return (progress.current_data >= progress.required_data and 
            progress.has_target_role and 
            progress.has_target_divisions)

def should_stop_for_max_pages(processed_count: int, process_config: ProcessConfig, progress: ProgressState) -> bool:
    max_pages_with_required_data = process_config.max_pages + progress.required_data
    return processed_count >= max_pages_with_required_data