from pydantic import BaseModel
from typing import List, Optional, Dict, TypeAlias, Generic, TypeVar
from enum import Enum
from domain.models import Person, Official
from domain.workflow_context import WorkflowContext

class SearchEngineStatus(Enum):
    NOT_STARTED = "not_started"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"

class SearchEngineState(BaseModel):
    links: List[str]
    status: str  # SearchEngineStatus value

class ProgressState(BaseModel):
    required_data: int
    current_data: int
    has_target_role: bool = (
        False  # Depends on the configs; might not have one. If so true by default
    )
    has_target_divisions: bool = (
        False  # Depends on municipal research. If none, true by default
    )

class LinkStatus(Enum):
    PENDING = "pending"
    SCRAPED = "scraped"
    PREPROCESSED = "preprocessed"
    PREPROCESSED_NO_CONTENT = "preprocessed_no_content"
    DONE = "done"
    ERROR = "error"

class Link(BaseModel):
    url: str
    status: str  # LinkStatus value
    folder_name: str = ""
    is_profile_page: bool = False

class RawLLMPerson(BaseModel):
    name: str
    roles: List[str]
    divisions: List[str]
    phone_number: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    image: Optional[str] = None


class LLMPerson(RawLLMPerson):
    source: str


class PeopleArrayLLMResponseSchema(BaseModel):
    people: List[RawLLMPerson]
    thought: str


OtherNamesByCanonicalName: TypeAlias = Dict[
    str, List[str]
]  # Canonical name to other names found while scraping
PeopleByName: TypeAlias = Dict[str, List[LLMPerson]]
RecordsByLLM: TypeAlias = Dict[str, PeopleByName]

class WorkflowConfig(BaseModel):
    url: str  # Municipality url. Without it we can't scrape anything.
    name: str # Human-readable name
    source_urls: Optional[List[str]] = None
    identities: Optional[Dict[str, List[str]]] = None # Canonical name to other names found while scraping
    
    # TODO: override in configs
    government_type: Optional[str] = None  # Ex: "Mayor-Council", "Council-Manager", etc.

class WorkflowStatus(Enum):
    INIT = "INIT"
    RESEARCH_MUNICIPALITY = "RESEARCH_MUNICIPALITY"
    SEARCH_LINKS = "SEARCH_LINKS"
    SCRAPE_PAGE = "SCRAPE_PAGE"
    PREPROCESS_PAGE_CONTENT = "PREPROCESS_PAGE_CONTENT"
    PROCESS_PAGE_CONTENT = "PROCESS_PAGE_CONTENT"
    MERGE_RECORDS_WITHIN_LLM = "MERGE_RECORDS_WITHIN_LLM"
    MERGE_RECORDS_ACROSS_LLMS = "MERGE_RECORDS_ACROSS_LLMS"
    FORMAT_OUTPUT = "FORMAT_OUTPUT",
    SAVE_OUTPUT = "SAVE_OUTPUT"
    CLEANUP = "CLEANUP"
    MAYBE_SEND_TO_GITHUB = "MAYBE_SEND_TO_GITHUB"
    RETRY = "RETRY"
    DONE = "DONE"

class FieldComparison(BaseModel):
    field: str
    merged_value: str
    llm_values: Dict[str, str]
    disagreement_score: float


class PersonDisagreements(BaseModel):
    person_name: str
    disagreements: List[FieldComparison]


class MissingPerson(BaseModel):
    name: str
    missing_from_llms: List[str]  # List of source names where this person was not found
    found_in_llms: List[str]  # List of source names where this person was found

class ResearchedPerson(BaseModel):
    name: str
    roles: List[str]
    divisions: List[str]

class ResearchMunicipalityStep(BaseModel):
    government_type: str
    people: List[ResearchedPerson]
    elected_officials: List[ResearchedPerson]
    notes: Optional[str] = None


class SearchLinksStep(BaseModel):
    search_link_pointer: int = 0  # Index of the next search engine to use
    search_engines: Dict[str, SearchEngineState] = {
        "google": SearchEngineState(links=[], status=SearchEngineStatus.NOT_STARTED.value),
        # "serpapi": SearchEngineState(links=[], status="not_started"),
        # "brave": SearchEngineState(links=[], status="not_started"),
        "crawl": SearchEngineState(links=[], status=SearchEngineStatus.NOT_STARTED.value),
    }  # e.g., "google": SearchEngineState
    error: Optional[str] = None

class PreprocessPageContentStep(BaseModel):
    elapsed_times: List[int] = []
    total_elapsed_time_seconds: int = 0
    average_elapsed_time_seconds: int = 0


class ProcessPageContentStep(BaseModel):
    raw_records_by_llm: RecordsByLLM
    records_by_llm: RecordsByLLM
    links: List[Link] = []
    progress: ProgressState = ProgressState(
        required_data=0, current_data=0, has_target_role=True, has_target_divisions=True
    )
    identities: OtherNamesByCanonicalName = {}


class MergeRecordsWithinLLMStep(BaseModel):
    people_by_llm: Dict[str, List[Person]]  # LLM Names to list of Person records




class MergeRecordsAcrossLLMsStep(BaseModel):
    people: List[Person]
    agreement_score: float
    disagreements: Dict[str, List[FieldComparison]] = {}
    missing_people: List[
        MissingPerson
    ] = []  # Now properly typed with MissingPerson class
    validation_errors: List[str] = []


class MaybeSendToGitHubStep(BaseModel):
    status: str
    response_status_code: Optional[int] = None
    response_text: Optional[str] = None

class PeopleCollectorData(BaseModel):
    jurisdiction_id: str

    # Can be overridden with data source configs
    config: WorkflowConfig 

    identities: Dict[str, List[str]] = {} 
    links: List[Link] = []
    progress: ProgressState = ProgressState(
        required_data=0, current_data=0, has_target_role=True, has_target_divisions=True
    )

    research_municipality_step: Optional[ResearchMunicipalityStep] = None
    search_links_step: SearchLinksStep = SearchLinksStep()
    preprocess_page_content_step: Optional[PreprocessPageContentStep] = None
    process_page_content_step: Optional[ProcessPageContentStep] = None
    merge_records_within_llm_step: Optional[MergeRecordsWithinLLMStep] = None
    merge_records_across_llms_step: Optional[MergeRecordsAcrossLLMsStep] = None
    maybe_send_to_github_step: Optional[MaybeSendToGitHubStep] = None
    format_output: Optional[List[Official]] = None 

    pipeline_duration: Optional[int] = None

class PeopleCollectorContext(WorkflowContext[PeopleCollectorData, WorkflowStatus]):
  request_id: str
