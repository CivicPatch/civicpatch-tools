from enum import Enum
from typing import Dict, List, Optional, TypeAlias

from domain.models import Official, Person
from domain.pipeline_run_context import PipelineRunContext
from pydantic import BaseModel, ConfigDict, Field
from runners.people_collector.steps.step_02_scrape_page.scrape_exceptions import (
    NavigationFailureReason,
)
from shared.schemas import (
    ExtractedPerson,
    PersonRecord,
    PipelineRunConfig,
    RoleConfig,
)
from shared.utils.statuses import PipelineRunStatus


class ProgressState(BaseModel):
    required_data: int
    current_data: int
    has_target_role: bool = False
    has_target_divisions: bool = False


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
    failure_reason: Optional[NavigationFailureReason] = None  # set when status=ERROR
    failure_source: Optional[str] = None  # raw Playwright/Chromium detail string
    visit_order: Optional[int] = None  # 1 = first page scraped, 2 = second, etc.
    attempts: int = 0  # scrape attempts spent, including the ones that failed


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

    def add_front(self, urls: List[str]) -> "LinkFrontier":
        """Add at the head of the queue, so these are scraped before anything already pending.

        For caller-supplied source URLs. Someone naming the page the roster is on is the
        strongest signal the pipeline gets, and it should not queue behind the jurisdiction's
        homepage — which is seeded first and otherwise wins by being there earlier.
        """
        from shared.utils.url_utils import canonical_url, format_url

        new_links = dict(self.links)
        added = []
        for url in urls:
            key = canonical_url(url)
            if key not in new_links:
                new_links[key] = Link(
                    url=format_url(url), status=LinkStatus.PENDING.value
                )
                added.append(key)
        return self.model_copy(
            update={"links": new_links, "queue": added + self.queue}
        )

    def dequeue(self, url: str) -> "LinkFrontier":
        from shared.utils.url_utils import canonical_url

        key = canonical_url(url)
        return self.model_copy(update={"queue": [k for k in self.queue if k != key]})

    def requeue(self, url: str, **updates) -> "LinkFrontier":
        """Send a link back to the tail of the queue, pending again.

        For a transient scrape failure: the pages already queued ahead of it are the delay,
        so a site that stalls for a few minutes gets retried once the crawl has moved on.
        """
        from shared.utils.url_utils import canonical_url

        key = canonical_url(url)
        if key not in self.links:
            return self
        new_link = self.links[key].model_copy(
            update={"status": LinkStatus.PENDING.value, **updates}
        )
        return self.model_copy(
            update={
                "links": {**self.links, key: new_link},
                "queue": [k for k in self.queue if k != key] + [key],
            }
        )

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


class PeopleArrayLLMResponseSchema(BaseModel):
    people: List[ExtractedPerson]
    # thought: str


class RelevantPageResponseSchema(BaseModel):
    is_relevant: bool
    relevant_urls: List[str] = []


OtherNamesByCanonicalName: TypeAlias = Dict[
    str, List[str]
]  # Canonical name to other names found while scraping
PeopleByName: TypeAlias = Dict[str, List[PersonRecord]]

PipelineStatus = PipelineRunStatus


class ResearchedPerson(BaseModel):
    """A name research turned up, and the office it named them under.

    `label` is verbatim, the same contract `ExtractedPerson.label` holds: one string as the
    source writes it, undecomposed.

    Nothing parses it here. On a jurisdiction cp.org has already published, posts *are* the
    parsed answer and this path does not run at all; on a cold start the label is a search
    term, which needs no structure.
    """

    name: str
    label: str = ""


class ResearchMunicipalityLLMSchema(BaseModel):
    people: List[ResearchedPerson]


class ResearchMunicipalityStep(BaseModel):
    expected_count: int = 0  # how many officials the pipeline expects to find
    # Who research thinks holds which office, labels verbatim. Only the cold-start path fills
    # it: once cp.org has posts, they are the same answer already parsed.
    researched: List[ResearchedPerson] = []
    target_divisions: List[str] = []  # geographic divisions to look for
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
    # Grouped by the name the page gave, because extraction fills it one page at a time.
    records: PeopleByName

    def all_records(self) -> List[PersonRecord]:
        return [record for group in self.records.values() for record in group]

    progress: ProgressState = ProgressState(
        required_data=0,
        current_data=0,
        has_target_role=False,
        has_target_divisions=False,
    )


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
    find_jurisdiction_url_step: Optional[FindJurisdictionUrlStep] = None
    send_success_step: Optional[MaybeSendToGitHubStep] = None
    send_error_step: Optional[MaybeSendToGitHubStep] = None
    issues: list[dict] = []
    error_step: Optional[str] = None
    error_detail: Optional[dict] = None


class PeopleCollectorContext(PipelineRunContext[PeopleCollectorData, PipelineStatus]):
    pass
