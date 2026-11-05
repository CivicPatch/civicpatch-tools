"""The issue this collector files: the run could not store what the classification says governs
the place. A state index that lists no charter is an answer, not a miss, so only a search that came
back empty-handed files it. A host that blocked us is its own type: the law may well be there."""

from typing import Optional

from .schemas import GoverningLawCollectorData, GoverningLawNotFound, Missing, TriedReason
from shared.schemas import FoundBy
from shared.utils.layered_config import GovernedBy
from shared.utils.statuses import PipelineIssueType

BLOCKED_REASONS = {TriedReason.REFUSED, TriedReason.CHALLENGED, TriedReason.DISALLOWED_BY_ROBOTS}


def issue_type(not_found: GoverningLawNotFound) -> PipelineIssueType:
    if any(tried.reason in BLOCKED_REASONS for tried in not_found.tried):
        return PipelineIssueType.SOURCE_BLOCKED
    return PipelineIssueType.GOVERNING_LAW_NOT_FOUND


def governing_law_not_found(data: GoverningLawCollectorData) -> Optional[GoverningLawNotFound]:
    answer = data.answer
    if answer is None or not (answer.urls or answer.tried):
        return None
    stored_anything = bool(data.charter_source_page_ids or data.general_law_source_page_ids)
    if not stored_anything:
        return GoverningLawNotFound(missing=Missing.EVERYTHING, tried=answer.tried, skipped_urls=data.skipped_urls)
    searched_in_vain = answer.found_by == FoundBy.SEARCH and not data.charter_source_page_ids
    if searched_in_vain and _may_have_a_charter(data):
        return GoverningLawNotFound(missing=Missing.CHARTER, tried=answer.tried, skipped_urls=data.skipped_urls)
    return None


def _may_have_a_charter(data: GoverningLawCollectorData) -> bool:
    governing_law = data.config.governing_law
    classification_id = data.answer.classification if data.answer else None
    if governing_law is None or classification_id is None:
        return False
    return governing_law.classifications[classification_id].governed_by != GovernedBy.GENERAL_LAW
