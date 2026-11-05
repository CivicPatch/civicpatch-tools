from decimal import Decimal
from enum import StrEnum
from typing import List, Optional

from domain.pipeline_run_context import PipelineRunContext
from pydantic import BaseModel, Field
from shared.schemas import FoundBy, GoverningLaw
from shared.utils.layered_config import GoverningLawConfig
from shared.utils.statuses import PipelineRunStatus


class GoverningLawCollectorStep(StrEnum):
    """The governing_law_collector's own steps; the lifecycle every pipeline shares is `PipelineRunStatus`."""

    FIND_SOURCES = "FIND_SOURCES"
    STORE_SOURCES = "STORE_SOURCES"
    WRITE_GOVERNING_LAW = "WRITE_GOVERNING_LAW"


GoverningLawCollectorState = PipelineRunStatus | GoverningLawCollectorStep


class GoverningLawCollectorConfig(BaseModel):
    """What cp.org answers at `/pipeline_runs/{id}/collector_config` for this kind."""

    name: str
    # The place's own site, where the search finder looks for its charter; many places have none.
    url: Optional[str] = None
    # Read by the engine, as the scrape's is; None inherits `pipeline.yml`'s default.
    pipeline_run_cap_usd: Optional[Decimal] = None
    # The state's merged block; None for a state that has none yet, which finds nothing.
    governing_law: Optional[GoverningLawConfig]


class TriedReason(StrEnum):
    REFUSED = "refused"
    CHALLENGED = "challenged"
    DISALLOWED_BY_ROBOTS = "disallowed_by_robots"
    OFF_LIMITS = "off_limits"
    FAILED = "failed"
    NOT_THE_TARGET = "not_the_target"
    # The place's own site, crawled to its budget without finding what was searched for.
    SITE_CRAWLED = "site_crawled"


class TriedUrl(BaseModel):
    url: str
    reason: TriedReason


class Missing(StrEnum):
    CHARTER = "charter"
    EVERYTHING = "everything"


class GoverningLawNotFound(BaseModel):
    """What the `governing_law_not_found` issue tells the human: what is missing, where the
    search looked and why each url was rejected, and which of the answer's urls the run skipped."""

    missing: Missing
    tried: List[TriedUrl]
    skipped_urls: List[str]


class LawKind(StrEnum):
    CONSTITUTION = "constitution"
    STATUTE = "statute"
    CHARTER = "charter"
    CODE = "code"


class LawUrl(BaseModel):
    url: str
    kind: LawKind
    # The text a search already read and approved, stored as it is; None for a url yet to be fetched.
    markdown: Optional[str] = Field(default=None, exclude=True)


class ReadPage(BaseModel):
    url: str
    markdown: str


def as_law_urls(urls: List[str], kind: LawKind) -> List[LawUrl]:
    return [LawUrl(url=url, kind=kind) for url in urls]


class LawTarget(BaseModel):
    """What a search looks for: everything in it that is particular to one kind of law."""

    kind: LawKind
    # How the question to the model names it: "municipal or county charter".
    description: str
    # What the state calls it; a link or sitemap entry naming one of these is followed first.
    terms: List[str]
    # A link naming one of these never is: a "charter school" is not the government's charter.
    skip_words: List[str] = []
    # The page check's labels that count as this target.
    kept_labels: List[str] = []


class SearchResult(BaseModel):
    law_urls: List[LawUrl] = []
    # Urls the search rejected, for the issue when nothing confirms.
    tried: List[TriedUrl] = []


class FinderAnswer(BaseModel):
    """What a finder says governs the jurisdiction, and where its texts are. The governing kind is
    not here: it follows from which of these texts the run actually stores."""

    found_by: FoundBy
    classification: Optional[str]
    law_urls: List[LawUrl] = []
    # Urls the search rejected, for the issue when nothing confirms; empty for the other finders.
    tried: List[TriedUrl] = []

    @property
    def urls(self) -> List[str]:
        return [law_url.url for law_url in self.law_urls]

    def urls_of(self, kind: LawKind) -> List[str]:
        return [law_url.url for law_url in self.law_urls if law_url.kind == kind]


class FetchedPage(BaseModel):
    url: str
    content_type: str
    body: bytes
    by_browser: bool


class GoverningLawCollectorData(BaseModel):
    jurisdiction_ocdid: str
    config: GoverningLawCollectorConfig
    answer: Optional[FinderAnswer] = None
    charter_source_page_ids: List[str] = []
    general_law_source_page_ids: List[str] = []
    # Urls a host refused (403, 429), or that stayed empty even by browser. Never retried.
    skipped_urls: List[str] = []
    governing_law: Optional[GoverningLaw] = None


class GoverningLawCollectorContext(PipelineRunContext[GoverningLawCollectorData, GoverningLawCollectorState]):
    pass
