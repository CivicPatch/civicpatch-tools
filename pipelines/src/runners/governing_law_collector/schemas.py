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

    FIND_SOURCE = "FIND_SOURCE"
    FETCH_SOURCE = "FETCH_SOURCE"
    PREPROCESS_PAGE_CONTENT = "PREPROCESS_PAGE_CONTENT"
    STORE_SOURCE_PAGE = "STORE_SOURCE_PAGE"
    CLASSIFY = "CLASSIFY"
    WRITE_GOVERNING_LAW = "WRITE_GOVERNING_LAW"


GoverningLawCollectorState = PipelineRunStatus | GoverningLawCollectorStep


class GoverningLawCollectorConfig(BaseModel):
    """What cp.org answers at `/pipeline_runs/{id}/governing_law_collector_config`."""

    name: str
    # Read by the engine, as the scrape's is; None inherits `pipeline.yml`'s default.
    pipeline_run_cap_usd: Optional[Decimal] = None
    # The state's merged block; None for a state that has none yet, which finds nothing.
    governing_law: Optional[GoverningLawConfig]


class FinderAnswer(BaseModel):
    """What a finder says governs the jurisdiction, and where its texts are. The kind is not
    here: it follows from which of these texts the run actually stores."""

    found_by: FoundBy
    classification: Optional[str]
    charter_urls: List[str] = []
    general_law_urls: List[str] = []

    @property
    def urls(self) -> List[str]:
        return [*self.charter_urls, *self.general_law_urls]


class FetchedPage(BaseModel):
    url: str
    content_type: str
    body: bytes
    by_browser: bool


class GoverningLawCollectorData(BaseModel):
    jurisdiction_ocdid: str
    config: GoverningLawCollectorConfig
    answer: Optional[FinderAnswer] = None
    # The answer's urls not yet stored, first one in hand.
    pending_urls: List[str] = []
    # The raw page and its markdown live only between their steps, and never in a saved context.
    fetched: Optional[FetchedPage] = Field(default=None, exclude=True)
    markdown: Optional[str] = Field(default=None, exclude=True)
    # The url in hand was thin by plain GET, so the next fetch of it is by browser.
    escalate: bool = False
    charter_source_page_ids: List[str] = []
    general_law_source_page_ids: List[str] = []
    # Urls a host refused (403, 429), or that stayed empty even by browser. Never retried.
    skipped_urls: List[str] = []
    governing_law: Optional[GoverningLaw] = None


class GoverningLawCollectorContext(PipelineRunContext[GoverningLawCollectorData, GoverningLawCollectorState]):
    pass
