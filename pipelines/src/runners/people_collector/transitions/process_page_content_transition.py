from decimal import Decimal
from typing import List

from runners.people_collector.schemas import (
  PipelineStatus,
  ProgressState,
  Link,
  LinkStatus
)
from shared.schemas import JobConfig
from shared.utils import url_utils

def next_process_content_state(
    processed_count: int,
    current_cost: Decimal,
    job_config: JobConfig,
    progress: ProgressState,
) -> tuple[PipelineStatus, str | None]:
    if should_stop_for_data_requirement(progress):
        return PipelineStatus.MERGE_RECORDS_WITHIN_LLM, None

    if should_stop_for_cost_limit(current_cost, job_config):
        return PipelineStatus.MERGE_RECORDS_WITHIN_LLM, "Cost limit reached before data requirements were met"

    if should_stop_for_max_pages(processed_count, job_config, progress):
        return PipelineStatus.MERGE_RECORDS_WITHIN_LLM, "Max pages reached before data requirements were met"

    return PipelineStatus.SCRAPE_PAGE, None


def get_next_link_with_status(links: List[Link], status: LinkStatus) -> Link | None:
    for link in links:
        if link.status == status.value:
            return link
    return None

def get_link_status_by_url(links: List[Link], url: str) -> LinkStatus | None:
    for link in links:
        if url_utils.same_url(link.url, url):
            return LinkStatus(link.status)
    return None

def should_stop_for_cost_limit(current_cost: Decimal, job_config: JobConfig) -> bool:
    return current_cost >= job_config.pipeline_run_cost_limit

def should_stop_for_data_requirement(progress: ProgressState) -> bool:
    return (progress.current_data >= progress.required_data and 
            progress.has_target_role and 
            progress.has_target_designations)

def should_stop_for_max_pages(processed_count: int, job_config: JobConfig, progress: ProgressState) -> bool:
    print("Processed count:", processed_count)
    print("Current progress:", progress)
    max_pages_with_required_data = job_config.max_pages + progress.required_data
    print("Max pages with required data:", max_pages_with_required_data)
    return processed_count >= max_pages_with_required_data
