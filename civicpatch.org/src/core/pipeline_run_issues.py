"""The issue a collector run files, from the report it sends at its end: the shared models each
pipeline's context extends (`shared.utils.run_reports`), read once from the uploaded context."""

from enum import StrEnum
from typing import Any, Callable, List, Optional

from pydantic import BaseModel
from shared.schemas import FoundBy
from shared.utils.layered_config import GovernedBy
from shared.utils.run_reports import GoverningLawReport, OrganizationsRunReport, RunOutcome, TriedUrl
from shared.utils.statuses import PipelineIssueType, PipelineRunKind, PipelineRunStatus


UNKNOWN_FAILURE = "the run ended in error without saying why"


class Missing(StrEnum):
    CHARTER = "charter"
    EVERYTHING = "everything"


class MissDetail(BaseModel):
    """What a person resolving a governing-law miss needs: what is missing and every url tried."""

    missing: Missing
    tried: List[TriedUrl]
    skipped_urls: List[str]


class FailureDetail(BaseModel):
    # `error` is what the issues page shows for a run-level issue.
    error: str
    failed_state: Optional[str] = None


class Issue(BaseModel):
    issue_type: PipelineIssueType
    data: dict[str, Any] = {}


def governing_law_issue(report: GoverningLawReport) -> Optional[Issue]:
    """Only a search can miss: a state index that names no charter is an answer."""
    if report.answer is None or report.answer.found_by != FoundBy.SEARCH:
        return None
    if not report.stored_anything:
        return _miss(report, Missing.EVERYTHING)
    if _missed_charter(report):
        return _miss(report, Missing.CHARTER)
    return None


def _missed_charter(report: GoverningLawReport) -> bool:
    """A search found no charter where the place may have one. Under `charter_else_general_law`, a
    clean search that found none is an answer: the general law governs, as in Oregon's counties."""
    if report.answer is None or report.answer.found_by != FoundBy.SEARCH or report.charter_source_page_ids:
        return False
    if report.governed_by in (None, GovernedBy.GENERAL_LAW):
        return False
    return report.blocked or report.governed_by != GovernedBy.CHARTER_ELSE_GENERAL_LAW


def _miss(report: GoverningLawReport, missing: Missing) -> Issue:
    issue_type = PipelineIssueType.SOURCE_BLOCKED if report.blocked else PipelineIssueType.GOVERNING_LAW_NOT_FOUND
    tried = report.answer.tried if report.answer else []
    detail = MissDetail(missing=missing, tried=tried, skipped_urls=report.skipped_urls)
    return Issue(issue_type=issue_type, data=detail.model_dump(mode="json"))


def organizations_issue(report: OrganizationsRunReport) -> Optional[Issue]:
    """No input hash means pipeline 2 had no law to read; the cap, that roles went unasked."""
    if report.input_hash is None:
        return Issue(issue_type=PipelineIssueType.NO_GOVERNING_LAW)
    if report.stopped_at_cost_cap:
        detail = report.cost_cap.model_dump(mode="json") if report.cost_cap else {}
        return Issue(issue_type=PipelineIssueType.COST_CAP_REACHED, data=detail)
    return None


def failure_issue(outcome: RunOutcome) -> Optional[Issue]:
    """A run that ended in error files `pipeline_error`, whatever its kind; nothing else it reports
    can be trusted then."""
    if outcome.current_state != PipelineRunStatus.ERROR:
        return None
    failure = outcome.failure
    detail = FailureDetail(error=failure.error, failed_state=failure.failed_state) if failure else FailureDetail(error=UNKNOWN_FAILURE)
    return Issue(issue_type=PipelineIssueType.PIPELINE_ERROR, data=detail.model_dump(mode="json"))


def run_issue(kind: PipelineRunKind, context: dict[str, Any]) -> Optional[Issue]:
    """The one issue a collector run files: its failure if it failed, else what its kind reads."""
    failed = failure_issue(RunOutcome.model_validate(context))
    if failed is not None:
        return failed
    return ISSUE_READERS[kind](context["data"])


def _read_governing_law(data: dict[str, Any]) -> Optional[Issue]:
    return governing_law_issue(GoverningLawReport.model_validate(data))


def _read_organizations(data: dict[str, Any]) -> Optional[Issue]:
    return organizations_issue(OrganizationsRunReport.model_validate(data))


# Each kind's context data, read into its report and decided.
ISSUE_READERS: dict[PipelineRunKind, Callable[[dict[str, Any]], Optional[Issue]]] = {
    PipelineRunKind.GOVERNING_LAW_COLLECTOR: _read_governing_law,
    PipelineRunKind.ORGANIZATIONS_COLLECTOR: _read_organizations,
}
