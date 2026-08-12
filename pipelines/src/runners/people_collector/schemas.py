from enum import Enum
from typing import Dict, List, Optional, TypeAlias

from domain.models import Official, Person
from domain.pipeline_run_context import PipelineRunContext
from pydantic import BaseModel, ConfigDict, Field
from shared.schemas import Issue, PipelineRunConfig
from shared.utils.config_utils import RoleConfig
from shared.utils.statuses import PipelineRunStatus


class ProgressState(BaseModel):
    required_data: int
    current_data: int
    has_target_role: bool = False
    has_target_designations: bool = False


class LinkStatus(Enum):
    PENDING = "pending"
    SCRAPED = "scraped"
    PREPROCESSED = "preprocessed"
    PREPROCESSED_NO_CONTENT = "preprocessed_no_content"
    PROCESSED_IRRELEVANT = "processed_irrelevant"
    PROCESSED_HEURISTICS_FAIL = "processed_heuristics_fail"
    DONE = "done"
    ERROR = "error"


class Link(BaseModel):
    url: str
    status: str  # LinkStatus value
    folder_name: str = ""
    num_references: int = 0
    comment: Optional[str] = None
    text: Optional[str] = None
    failure_reason: Optional[str] = (
        None  # NavigationFailureReason value, set when status=ERROR
    )
    failure_source: Optional[str] = None  # raw Playwright/Chromium detail string
    visit_order: Optional[int] = None  # 1 = first page scraped, 2 = second, etc.


class LinkFrontier(BaseModel):
    """Encapsulates the link dict and pending queue so they always stay in sync."""

    model_config = ConfigDict(frozen=True)

    links: Dict[str, "Link"] = {}  # canonical_url(link.url) → Link
    queue: List[str] = []  # canonical URLs of PENDING links, priority-sorted

    @classmethod
    def from_urls(cls, urls: List[str]) -> "LinkFrontier":
        from shared.utils.url_utils import canonical_url, format_url

        links = {}
        queue = []
        for url in urls:
            key = canonical_url(url)
            if key not in links:
                links[key] = Link(url=format_url(url), status=LinkStatus.PENDING.value)
                queue.append(key)
        return cls(links=links, queue=queue)

    # ── Queries ────────────────────────────────────────────────────────────────

    def get(self, url: str) -> Optional["Link"]:
        from shared.utils.url_utils import canonical_url

        return self.links.get(canonical_url(url))

    def status_of(self, url: str) -> Optional["LinkStatus"]:
        link = self.get(url)
        return LinkStatus(link.status) if link else None

    def next_pending(self) -> Optional["Link"]:
        return self.links[self.queue[0]] if self.queue else None

    def next_with_status(self, status: "LinkStatus") -> Optional["Link"]:
        if status == LinkStatus.PENDING:
            return self.next_pending()
        return next((l for l in self.links.values() if l.status == status.value), None)

    def all_with_status(self, statuses: List["LinkStatus"]) -> List["Link"]:
        vals = {s.value for s in statuses}
        return [l for l in self.links.values() if l.status in vals]

    def __len__(self) -> int:
        return len(self.links)

    def __bool__(self) -> bool:
        return bool(self.links)

    # ── Mutations (return new LinkFrontier) ────────────────────────────────────

    def add(self, urls: List[str]) -> "LinkFrontier":
        from shared.utils.url_utils import canonical_url, format_url

        new_links = dict(self.links)
        new_queue = list(self.queue)
        for url in urls:
            key = canonical_url(url)
            if key not in new_links:
                new_links[key] = Link(
                    url=format_url(url), status=LinkStatus.PENDING.value
                )
                new_queue.append(key)
        return self.model_copy(update={"links": new_links, "queue": new_queue})

    def dequeue(self, url: str) -> "LinkFrontier":
        from shared.utils.url_utils import canonical_url

        key = canonical_url(url)
        return self.model_copy(update={"queue": [k for k in self.queue if k != key]})

    def update_link(self, lookup_url: str, **updates) -> "LinkFrontier":
        from shared.utils.url_utils import canonical_url

        key = canonical_url(lookup_url)
        if key not in self.links:
            return self
        return self.model_copy(
            update={
                "links": {**self.links, key: self.links[key].model_copy(update=updates)}
            }
        )

    def mark_status(self, url: str, status: "LinkStatus", **extra) -> "LinkFrontier":
        from shared.utils.url_utils import canonical_url

        key = canonical_url(url)
        if key not in self.links:
            return self
        new_link = self.links[key].model_copy(update={"status": status.value, **extra})
        new_links = {**self.links, key: new_link}
        new_queue = (
            [k for k in self.queue if k != key]
            if status != LinkStatus.PENDING
            else self.queue
        )
        return self.model_copy(update={"links": new_links, "queue": new_queue})


class RawLLMPersonRecord(BaseModel):
    name: str
    roles: List[str]
    designations: List[str]

    phone: Optional[str] = None
    email: Optional[str] = None
    url: Optional[str] = None

    start_date: Optional[str] = None
    end_date: Optional[str] = None
    image: Optional[str] = None


class PeopleArrayLLMResponseSchema(BaseModel):
    people: List[RawLLMPersonRecord]
    # thought: str


class RelevantPageResponseSchema(BaseModel):
    is_relevant: bool
    relevant_urls: List[str] = []


class UnrecognizedRole(BaseModel):
    role: str
    person_name: str


class LLMPersonRecord(RawLLMPersonRecord):
    source_url: str


OtherNamesByCanonicalName: TypeAlias = Dict[
    str, List[str]
]  # Canonical name to other names found while scraping
PeopleByName: TypeAlias = Dict[str, List[LLMPersonRecord]]

PipelineStatus = PipelineRunStatus


class ResearchedPerson(BaseModel):
    name: str
    roles: List[str]
    designations: List[str]


class ResearchMunicipalityLLMSchema(BaseModel):
    people: List[ResearchedPerson]


class ResearchMunicipalityStep(BaseModel):
    expected_count: int = 0  # how many officials the pipeline expects to find
    target_designations: List[str] = []  # geographic designations to look for
    known_roles: list[str] = []
    identities: dict[
        str, list[str]
    ] = {}  # canonical name to list of other names/aliases
    source_urls: list[str] = []
    notes: Optional[str] = None
    origin_source: str = "google_gemini"


class PreprocessPageContentStep(BaseModel):
    elapsed_times: List[int] = []
    total_elapsed_time_seconds: int = 0
    average_elapsed_time_seconds: int = 0


class ProcessPageContentStep(BaseModel):
    records: PeopleByName
    progress: ProgressState = ProgressState(
        required_data=0,
        current_data=0,
        has_target_role=False,
        has_target_designations=False,
    )


class MergeRecordsWithinLLMStep(BaseModel):
    records: List[Person]  # LLM Names to list of Person records
    unrecognized_roles: List[UnrecognizedRole] = []
    excluded_people: List[Person] = []


class FormatOutputStep(BaseModel):
    officials: List[Official]


class ReviewOutputStep(BaseModel):
    issues: List[Issue]
    people_by_source: List[dict]
    origin_source: str = "google_gemini"


class FindJurisdictionUrlStep(BaseModel):
    discovered_url: Optional[str] = None


class OfficialJurisdictionUrlResponseSchema(BaseModel):
    is_official_jurisdiction_url: bool


class MaybeSendToGitHubStep(BaseModel):
    status: str
    response_status_code: Optional[int] = None
    response_text: Optional[str] = None


class PeopleCollectorData(BaseModel):
    jurisdiction_ocdid: str

    # Can be overridden with data source configs
    config: PipelineRunConfig

    role_config: Optional[RoleConfig] = Field(default=None, exclude=True)

    frontier: LinkFrontier = Field(default_factory=LinkFrontier)

    research_municipality_step: Optional[ResearchMunicipalityStep] = None
    preprocess_page_content_step: Optional[PreprocessPageContentStep] = None
    process_page_content_step: Optional[ProcessPageContentStep] = None
    merge_records_within_llm_step: Optional[MergeRecordsWithinLLMStep] = None
    format_output_step: Optional[FormatOutputStep] = None
    review_output_step: Optional[ReviewOutputStep] = None
    find_jurisdiction_url_step: Optional[FindJurisdictionUrlStep] = None
    send_success_step: Optional[MaybeSendToGitHubStep] = None
    send_error_step: Optional[MaybeSendToGitHubStep] = None
    issues: list[dict] = []
    error_step: Optional[str] = None
    error_detail: Optional[dict] = None


class PeopleCollectorContext(PipelineRunContext[PeopleCollectorData, PipelineStatus]):
    pass
