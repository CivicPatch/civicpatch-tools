from decimal import Decimal
from typing import List

from jobs.people_collector.schemas import (
  WorkflowStatus,
  ProgressState,
  Link,
  LinkStatus
)
from shared.schemas import JobConfig

def next_state_for_process_content_state(
    processed_count: int,
    current_cost: Decimal,
    job_config: JobConfig,
    progress: ProgressState
) -> WorkflowStatus:
    if should_stop_for_cost_limit(current_cost, job_config):
        return WorkflowStatus.MERGE_RECORDS_WITHIN_LLM
    
    if should_stop_for_data_requirement(progress):
        return WorkflowStatus.MERGE_RECORDS_WITHIN_LLM
    
    if should_stop_for_max_pages(processed_count, job_config, progress):
        return WorkflowStatus.MERGE_RECORDS_WITHIN_LLM
    
    return WorkflowStatus.SCRAPE_PAGE

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

def should_stop_for_cost_limit(current_cost: Decimal, job_config: JobConfig) -> bool:
    return current_cost >= job_config.pipeline_run_cost_limit

def should_stop_for_data_requirement(progress: ProgressState) -> bool:
    return (progress.current_data >= progress.required_data and 
            progress.has_target_role and 
            progress.has_target_divisions)

def should_stop_for_max_pages(processed_count: int, job_config: JobConfig, progress: ProgressState) -> bool:
    max_pages_with_required_data = job_config.max_pages + progress.required_data
    return processed_count >= max_pages_with_required_data
