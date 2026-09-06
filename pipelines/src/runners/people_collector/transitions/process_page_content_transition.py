from decimal import Decimal
from typing import List

from runners.people_collector.schemas import (
  PipelineStatus,
  ProgressState,
  Link,
  LinkStatus
)
from shared.schemas import PipelineRunLimits
from shared.utils import url_utils
from shared.utils.statuses import PipelineIssueType


# Why the crawl stopped, when it stopped early. `None` is "it did not" and the fourth case —
# having found what it came for — is a *good* stop and needs no reason.
#
# A reason rather than a message, because one of these now has to reach the reviewer as an
# issue and not only the run log; comparing log strings to decide that would be worse.
STOP_COST_CAP = PipelineIssueType.COST_CAP_REACHED
STOP_MAX_PAGES = "max_pages_reached"

STOP_MESSAGES = {
    STOP_COST_CAP: "Cost limit reached before data requirements were met",
    STOP_MAX_PAGES: "Max pages reached before data requirements were met",
}

def next_process_content_state(
    processed_count: int,
    current_cost: Decimal,
    limits: PipelineRunLimits,
    progress: ProgressState,
) -> tuple[PipelineStatus, str | None]:
    if should_stop_for_data_requirement(progress):
        return PipelineStatus.CLEANUP, None

    if should_stop_for_cap(current_cost, limits):
        return PipelineStatus.CLEANUP, STOP_COST_CAP

    if should_stop_for_max_pages(processed_count, limits, progress):
        return PipelineStatus.CLEANUP, STOP_MAX_PAGES

    return PipelineStatus.SCRAPE_PAGE, None



def should_stop_for_cap(current_cost: Decimal, limits: PipelineRunLimits) -> bool:
    return current_cost >= limits.pipeline_run_cap_usd

# `required_data` is the size of the roster we already hold, so it is an expectation, not a
# fact — a council that lost a member leaves it permanently unreachable. Seattle, 2026-08-17:
# 10 found against 11 expected, both target flags satisfied, and the run crawled to its page
# cap for the missing one. Treated as a target to get close to rather than a wall.
DATA_REQUIREMENT_TOLERANCE = 2


def should_stop_for_data_requirement(progress: ProgressState) -> bool:
    found_enough = progress.current_data >= progress.required_data - DATA_REQUIREMENT_TOLERANCE
    return found_enough and progress.has_target_role and progress.has_target_divisions

def is_short_of_expected(progress: ProgressState) -> bool:
    """Short by more than the tolerance above — the same slack `should_stop_for_data_requirement`
    allows, so the two readings of "enough" cannot disagree."""
    return progress.current_data < progress.required_data - DATA_REQUIREMENT_TOLERANCE


def should_stop_for_max_pages(processed_count: int, limits: PipelineRunLimits, progress: ProgressState) -> bool:
    return processed_count >= max_pages_allowed(limits, progress)


def max_pages_allowed(limits: PipelineRunLimits, progress: ProgressState) -> int:
    return limits.max_pages + progress.required_data


def describe_progress(
    processed_count: int, current_cost: Decimal, limits: PipelineRunLimits, progress: ProgressState
) -> str:
    """One line per processed page, for the run log. Every stop condition is in it, so a run
    that keeps going says which requirement is still unmet — the question that took a container
    shell to answer before."""
    return (
        f"Progress: {progress.current_data}/{progress.required_data} people "
        f"(tolerance {DATA_REQUIREMENT_TOLERANCE}) · "
        f"role={'y' if progress.has_target_role else 'n'} "
        f"divisions={'y' if progress.has_target_divisions else 'n'} · "
        f"pages {processed_count}/{max_pages_allowed(limits, progress)} · "
        f"cost ${current_cost:.4f}/${limits.pipeline_run_cap_usd}"
    )
