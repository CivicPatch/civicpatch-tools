"""The issue any run files when it ended in error, whatever its kind."""

from typing import Any, Optional

from pydantic import BaseModel
from shared.utils.run_reports import RunFailure, RunOutcome
from shared.utils.statuses import RUN_LEVEL_ISSUE_TYPES, PipelineIssueType, PipelineRunErrorType, PipelineRunStatus
from .issue import Issue


UNKNOWN_FAILURE = "the run ended in error without saying why"
# Where an error step that is no known type goes, so the detail keeps it.
REPORTED_ERROR_STEP = "reported_error_step"


class FailureDetail(BaseModel):
    # `error` is what the issues page shows for a run-level issue.
    error: str
    failed_state: Optional[str] = None


def crash_issue(failure: Optional[RunFailure]) -> Optional[Issue]:
    """A step that raised, as the engine recorded it. People collector reports from SEND_ERROR,
    before its context says ERROR, so this reads the failure alone; None when nothing raised."""
    if failure is None:
        return None
    detail = FailureDetail(error=failure.error, failed_state=failure.failed_state)
    return Issue(issue_type=PipelineIssueType.PIPELINE_ERROR, data=detail.model_dump(mode="json"))


def unknown_failure_issue() -> Issue:
    detail = FailureDetail(error=UNKNOWN_FAILURE)
    return Issue(issue_type=PipelineIssueType.PIPELINE_ERROR, data=detail.model_dump(mode="json"))


def failure_issue(outcome: RunOutcome) -> Optional[Issue]:
    """A run that ended in error files `pipeline_error`, whatever its kind; nothing else it reports
    can be trusted then."""
    if outcome.current_state != PipelineRunStatus.ERROR:
        return None
    crash = crash_issue(outcome.failure)
    if crash is not None:
        return crash
    return unknown_failure_issue()


def run_level_type(error_type: Optional[str]) -> PipelineIssueType | PipelineRunErrorType | None:
    """A raw exception string once became an issue type: an error step is filed as itself only if it is one."""
    return next((known for known in RUN_LEVEL_ISSUE_TYPES if known == error_type), None)


def reported_failure_issue(failure: Optional[RunFailure], error_step: Optional[str], error_detail: dict[str, Any]) -> Issue:
    """People collector's error path: the engine's crash wins over any error step the context also has."""
    crash = crash_issue(failure)
    if crash is not None:
        return crash
    known = run_level_type(error_step)
    if error_step and known is None:
        return Issue(issue_type=PipelineIssueType.PIPELINE_ERROR, data={**error_detail, REPORTED_ERROR_STEP: error_step})
    if not error_step and not error_detail:
        return unknown_failure_issue()
    return Issue(issue_type=known or PipelineIssueType.PIPELINE_ERROR, data=error_detail)


def settled_run_issue(error_type: str, error_detail: Optional[dict[str, Any]], last_seen: Optional[dict[str, Any]]) -> Issue:
    """A run that reached no report: the workflow settled it, with the last status it was seen in."""
    detail = dict(error_detail or {})
    if last_seen is not None:
        detail.setdefault("last_status", last_seen["status"])
        detail.setdefault("last_progress", last_seen["progress"])
    return Issue(issue_type=run_level_type(error_type) or PipelineIssueType.PIPELINE_ERROR, data=detail)
