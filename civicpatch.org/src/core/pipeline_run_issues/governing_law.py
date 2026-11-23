"""Pipeline 1's issue, from its report: a search that missed the law the place's classification expects."""

from enum import StrEnum
from typing import Any, List, Optional

from pydantic import BaseModel
from shared.schemas import FoundBy
from shared.utils.layered_config import GovernedBy
from shared.utils.run_reports import GoverningLawReport, TriedUrl
from shared.utils.statuses import PipelineIssueType
from .issue import Issue


class Missing(StrEnum):
    CHARTER = "charter"
    EVERYTHING = "everything"


class MissDetail(BaseModel):
    """What a person resolving a governing-law miss needs: what is missing and every url tried."""

    missing: Missing
    tried: List[TriedUrl]
    skipped_urls: List[str]


def governing_law_issue(report: GoverningLawReport) -> Optional[Issue]:
    """Only a search can miss: a state index that names no charter is an answer."""
    if report.answer is None or report.answer.found_by != FoundBy.SEARCH:
        return None
    if not report.stored_anything:
        return _miss(report, Missing.EVERYTHING)
    if _missed_charter(report):
        return _miss(report, Missing.CHARTER)
    return None


def read(data: dict[str, Any]) -> Optional[Issue]:
    return governing_law_issue(GoverningLawReport.model_validate(data))


def _missed_charter(report: GoverningLawReport) -> bool:
    """A search found no charter where the place may have one. Only where every place has one
    (`charter`) is a clean search that found none a miss; where only some do (Maine's towns, Oregon's
    counties) it is the answer, and the general law governs."""
    if report.answer is None or report.answer.found_by != FoundBy.SEARCH or report.charter_source_page_ids:
        return False
    if report.governed_by in (None, GovernedBy.GENERAL_LAW):
        return False
    return report.blocked or report.governed_by == GovernedBy.CHARTER


def _miss(report: GoverningLawReport, missing: Missing) -> Issue:
    issue_type = PipelineIssueType.SOURCE_BLOCKED if report.blocked else PipelineIssueType.GOVERNING_LAW_NOT_FOUND
    tried = report.answer.tried if report.answer else []
    detail = MissDetail(missing=missing, tried=tried, skipped_urls=report.skipped_urls)
    return Issue(issue_type=issue_type, data=detail.model_dump(mode="json"))
