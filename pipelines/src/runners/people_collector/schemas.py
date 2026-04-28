from pydantic import BaseModel, Field
from typing import List, Optional, Dict, TypeAlias
from enum import Enum
from domain.models import Person, Official
from domain.pipeline_run_context import PipelineRunContext
from shared.schemas import PipelineRunConfig
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
    PROCESSED_HEURISTICS_FAIL  = "processed_heuristics_fail"
    DONE = "done"
    ERROR = "error"

class Link(BaseModel):
    url: str
    status: str  # LinkStatus value
    folder_name: str = ""
    num_references: int = 0
    comment: Optional[str] = None
    text: Optional[str] = None
    failure_reason: Optional[str] = None  # NavigationFailureReason value, set when status=ERROR
    failure_source: Optional[str] = None  # raw Playwright/Chromium detail string

class RawLLMPerson(BaseModel):
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
    people: List[RawLLMPerson]
    # thought: str

class RelevantPageResponseSchema(BaseModel):
    is_relevant: bool
    relevant_urls: List[str] = []

class UnrecognizedRole(BaseModel):
    role: str
    person_name: str

class ExcludedPerson(BaseModel):
    name: str
    roles: List[str]
    designations: List[str] = []
    source_urls: List[str] = []

class LLMPerson(RawLLMPerson):
    source_url: str

OtherNamesByCanonicalName: TypeAlias = Dict[
    str, List[str]
]  # Canonical name to other names found while scraping
PeopleByName: TypeAlias = Dict[str, List[LLMPerson]]
RecordsByLLM: TypeAlias = Dict[str, PeopleByName]

PipelineStatus = PipelineRunStatus

class ResearchedPerson(BaseModel):
    name: str
    roles: List[str]
    designations: List[str]

class ResearchMunicipalityLLMSchema(BaseModel):
    people: List[ResearchedPerson]

class ResearchMunicipalityStep(BaseModel):
    expected_count: int = 0         # how many officials the pipeline expects to find
    target_designations: List[str] = []  # geographic designations to look for
    known_roles: list[str] = []
    identities: dict[str, list[str]] = {}  # canonical name to list of other names/aliases
    source_urls: list[str] = []
    notes: Optional[str] = None
    origin_source: str = "google_gemini"

class PreprocessPageContentStep(BaseModel):
    elapsed_times: List[int] = []
    total_elapsed_time_seconds: int = 0
    average_elapsed_time_seconds: int = 0


class ProcessPageContentStep(BaseModel):
    raw_records_by_llm: RecordsByLLM
    records_by_llm: RecordsByLLM
    progress: ProgressState = ProgressState(
        required_data=0, current_data=0, has_target_role=False, has_target_designations=False
    )

class MergeRecordsWithinLLMStep(BaseModel):
    people_by_llm: Dict[str, List[Person]]  # LLM Names to list of Person records
    unrecognized_roles: List[UnrecognizedRole] = []
    excluded_people: List[ExcludedPerson] = []

class MergeRecordsAcrossLLMsStep(BaseModel):
    people: List[Person]

class FormatOutputStep(BaseModel):
    officials: List[Official]

class ReviewOutputStep(BaseModel):
    issues: List[str]
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

    links: List[Link] = []

    research_municipality_step: Optional[ResearchMunicipalityStep] = None
    preprocess_page_content_step: Optional[PreprocessPageContentStep] = None
    process_page_content_step: Optional[ProcessPageContentStep] = None
    merge_records_within_llm_step: Optional[MergeRecordsWithinLLMStep] = None
    merge_records_across_llms_step: Optional[MergeRecordsAcrossLLMsStep] = None
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