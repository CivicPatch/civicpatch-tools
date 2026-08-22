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
        return PipelineStatus.CLEANUP, None

    if should_stop_for_cost_limit(current_cost, job_config):
        return PipelineStatus.CLEANUP, "Cost limit reached before data requirements were met"

    if should_stop_for_max_pages(processed_count, job_config, progress):
        return PipelineStatus.CLEANUP, "Max pages reached before data requirements were met"

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
    return processed_count >= max_pages_allowed(job_config, progress)


def max_pages_allowed(job_config: JobConfig, progress: ProgressState) -> int:
    return job_config.max_pages + progress.required_data


def describe_progress(
    processed_count: int, current_cost: Decimal, job_config: JobConfig, progress: ProgressState
) -> str:
    """One line per processed page, for the run log. Every stop condition is in it, so a run
    that keeps going says which requirement is still unmet — the question that took a container
    shell to answer before."""
    return (
        f"Progress: {progress.current_data}/{progress.required_data} people "
        f"(tolerance {DATA_REQUIREMENT_TOLERANCE}) · "
        f"role={'y' if progress.has_target_role else 'n'} "
        f"divisions={'y' if progress.has_target_divisions else 'n'} · "
        f"pages {processed_count}/{max_pages_allowed(job_config, progress)} · "
        f"cost ${current_cost:.4f}/${job_config.pipeline_run_cost_limit}"
    )
