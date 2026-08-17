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



def should_stop_for_cost_limit(current_cost: Decimal, job_config: JobConfig) -> bool:
    return current_cost >= job_config.pipeline_run_cost_limit

# `required_data` is the size of the roster we already hold, so it is an expectation, not a
# fact — a council that lost a member leaves it permanently unreachable. Seattle, 2026-08-17:
# 10 found against 11 expected, both target flags satisfied, and the run crawled to its page
# cap for the missing one. Treated as a target to get close to rather than a wall.
DATA_REQUIREMENT_TOLERANCE = 2


def should_stop_for_data_requirement(progress: ProgressState) -> bool:
    found_enough = progress.current_data >= progress.required_data - DATA_REQUIREMENT_TOLERANCE
    return found_enough and progress.has_target_role and progress.has_target_divisions

def should_stop_for_max_pages(processed_count: int, job_config: JobConfig, progress: ProgressState) -> bool:
    print("Processed count:", processed_count)
    print("Current progress:", progress)
    max_pages_with_required_data = job_config.max_pages + progress.required_data
    print("Max pages with required data:", max_pages_with_required_data)
    return processed_count >= max_pages_with_required_data
