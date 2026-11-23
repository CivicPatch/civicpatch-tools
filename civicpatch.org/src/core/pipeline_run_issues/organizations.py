"""Pipeline 2's issue, from its report."""

from typing import Any, Optional

from shared.utils.run_reports import OrganizationsRunReport, TriedReason, TriedUrl
from shared.utils.statuses import PipelineIssueType
from .governing_law import MissDetail, Missing
from .issue import Issue


def organizations_issue(report: OrganizationsRunReport) -> Optional[Issue]:
    """No input hash means pipeline 2 had no law to read; the cap, that roles went unasked; an unquoted
    charter, that pipeline 1 stored a page that is not the charter."""
    if report.input_hash is None:
        return Issue(issue_type=PipelineIssueType.NO_GOVERNING_LAW)
    if report.stopped_at_cost_cap:
        detail = report.cost_cap.model_dump(mode="json") if report.cost_cap else {}
        return Issue(issue_type=PipelineIssueType.COST_CAP_REACHED, data=detail)
    if report.unquoted_charter_urls:
        tried = [TriedUrl(url=url, reason=TriedReason.NOT_THE_TARGET) for url in report.unquoted_charter_urls]
        detail = MissDetail(missing=Missing.CHARTER, tried=tried, skipped_urls=[])
        return Issue(issue_type=PipelineIssueType.GOVERNING_LAW_NOT_FOUND, data=detail.model_dump(mode="json"))
    return None


def read(data: dict[str, Any]) -> Optional[Issue]:
    return organizations_issue(OrganizationsRunReport.model_validate(data))
