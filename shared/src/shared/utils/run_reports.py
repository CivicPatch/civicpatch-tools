"""What a collector run reports at its end, the part of its context cp.org reads to file the run's issue.
Each pipeline's own data model extends these, so the fields that cross the boundary are defined once."""

from decimal import Decimal
from enum import StrEnum
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel
from shared.schemas import FoundBy
from shared.utils.layered_config import GovernedBy


class TriedReason(StrEnum):
    REFUSED = "refused"
    CHALLENGED = "challenged"
    DISALLOWED_BY_ROBOTS = "disallowed_by_robots"
    OFF_LIMITS = "off_limits"
    FAILED = "failed"
    NOT_THE_TARGET = "not_the_target"
    # The place's own site, crawled to its budget without finding what was searched for.
    SITE_CRAWLED = "site_crawled"


# A host that kept us out: the law may well be there.
BLOCKED_REASONS = frozenset({TriedReason.REFUSED, TriedReason.CHALLENGED, TriedReason.DISALLOWED_BY_ROBOTS})


class TriedUrl(BaseModel):
    url: str
    reason: TriedReason


class GoverningLawSearch(BaseModel):
    """How a finder answered, without the texts it found."""

    found_by: FoundBy
    classification: Optional[str]
    # Urls the search rejected, for the issue when nothing confirms; empty for the other finders.
    tried: List[TriedUrl] = []


TSearch = TypeVar("TSearch", bound=GoverningLawSearch)


class GoverningLawRunReport(BaseModel, Generic[TSearch]):
    answer: Optional[TSearch] = None
    charter_source_page_ids: List[str] = []
    general_law_source_page_ids: List[str] = []
    # Urls a host refused (403, 429), or that stayed empty even by browser. Never retried.
    skipped_urls: List[str] = []
    # How the place's classification is governed, from the state's config; None with no classification.
    governed_by: Optional[GovernedBy] = None

    @property
    def stored_anything(self) -> bool:
        return bool(self.charter_source_page_ids or self.general_law_source_page_ids)

    @property
    def blocked(self) -> bool:
        return self.answer is not None and any(tried.reason in BLOCKED_REASONS for tried in self.answer.tried)


# What cp.org reads: the search without a pipeline's own fields.
GoverningLawReport = GoverningLawRunReport[GoverningLawSearch]


class CostCapDetail(BaseModel):
    """`cost_cap_reached`'s detail in every pipeline: the spend against the cap, and the work left undone
    (pipeline 2's unasked role ids; pipeline 3's uncrawled pages, when it moves over)."""

    spent_usd: Decimal
    cap_usd: Decimal
    unfinished: List[str] = []


class OrganizationsRunReport(BaseModel):
    # The hash of what the run read and asked; None when there was no law to read.
    input_hash: Optional[str] = None
    # The run's cap was reached before every question was asked; `cost_cap` says what was left.
    stopped_at_cost_cap: bool = False
    cost_cap: Optional[CostCapDetail] = None


class RunFailure(BaseModel):
    """Why a run ended in error: the state whose step raised, and what it raised."""

    failed_state: str
    error: str


class RunOutcome(BaseModel):
    """Every run's context, whatever its pipeline: how it ended."""

    current_state: str
    failure: Optional[RunFailure] = None
