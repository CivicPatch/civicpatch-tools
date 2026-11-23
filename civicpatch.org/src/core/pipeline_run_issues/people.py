"""Pipeline 3's issue, from its report. One at most: a capped run is already short and already says so."""

from typing import Any, Optional

from shared.utils.run_reports import PeopleRunReport
from shared.utils.statuses import PipelineIssueType
from .issue import Issue


def people_issue(report: PeopleRunReport) -> Optional[Issue]:
    if report.stopped_at_cost_cap:
        return Issue(issue_type=PipelineIssueType.COST_CAP_REACHED)
    if report.shortfall is not None:
        return Issue(issue_type=PipelineIssueType.FEWER_THAN_EXPECTED, data=report.shortfall.model_dump(mode="json"))
    return None


def read(data: dict[str, Any]) -> Optional[Issue]:
    return people_issue(PeopleRunReport.model_validate(data))
