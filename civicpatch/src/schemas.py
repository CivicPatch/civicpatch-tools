from typing import Dict, List, Optional, TypeAlias, Any, Callable, Union, NamedTuple, Literal
from pydantic import BaseModel, field_validator
from enum import Enum

class JurisdictionId(BaseModel):
    country: str
    state: str
    county: Optional[str] = None
    place: str = None

class SearchEngineStatus(Enum):
    NOT_STARTED = "not_started"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"

class SearchEngineState(BaseModel):
    links: List[str]
    status: str # SearchEngineStatus value 

class ProgressState(BaseModel):
    required_data: int
    current_data: int
    has_target_role: bool # Depends on the configs; might not have one. If so true by default
    has_target_divisions: bool # Depends on municipal research. If none, true by default

class LinkStatus(Enum):
    PENDING = "pending"
    SCRAPED = "scraped"
    PREPROCESSED = "preprocessed"
    PREPROCESSED_NO_CONTENT = "preprocessed_no_content"
    DONE = "done"
    ERROR = "error"

class Link(BaseModel):
    url: str
    status: str # LinkStatus value
    folder_name: str = ""
    is_profile_page: bool = False

class PipelineStatus(Enum):
    INIT = "INIT"
    RESEARCH_MUNICIPALITY = "RESEARCH_MUNICIPALITY"
    SEARCH_LINKS = "SEARCH_LINKS"
    SCRAPE_PAGE = "SCRAPE_PAGE"
    PREPROCESS_PAGE_CONTENT = "PREPROCESS_PAGE_CONTENT"
    PROCESS_PAGE_CONTENT = "PROCESS_PAGE_CONTENT"
    MERGE_RECORDS_WITHIN_LLM = "MERGE_RECORDS_WITHIN_LLM"
    MERGE_RECORDS_ACROSS_LLMS = "MERGE_RECORDS_ACROSS_LLMS"
    MAYBE_SEND_TO_GITHUB = "MAYBE_SEND_TO_GITHUB"
    CLEANUP = "CLEANUP"
    RETRY = "RETRY"
    DONE = "DONE"

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

class Person(RawLLMPerson):
    cdn_image: str
    jurisdiction_id: str
    sources: List[str] # List of source URLs where information was found
    updated_at: str

OtherNamesByCanonicalName: TypeAlias = Dict[str, List[str]] # Canonical name to other names found while scraping
PeopleByName: TypeAlias = Dict[str, List[LLMPerson]]
RecordsByLLM: TypeAlias = Dict[str, PeopleByName]

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
    search_engines: Dict[str, SearchEngineState]  # e.g., "google": SearchEngineState
    links: List[Link]

class ProcessPageContentStep(BaseModel):
    raw_records_by_llm: RecordsByLLM
    records_by_llm: RecordsByLLM

class MergeRecordsWithinLLMStep(BaseModel):
    people_by_llm: Dict[str, List[Person]] # LLM Names to list of Person records

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

class MergeRecordsAcrossLLMsStep(BaseModel):
    people: List[Person]
    agreement_score: float
    disagreements: Dict[str, List[FieldComparison]] = {}
    missing_people: List[MissingPerson] = []  # Now properly typed with MissingPerson class
    validation_errors: List[str] = []

class PipelineRequest(BaseModel):
    name: str # Human-readable name -- typically this would include the lsad (ex: Naperville township)
    jurisdiction_id: str # Format: ocd-jurisdiction/country:us/state:wa/place:seattle
                         # OR ocd-jurisdiction/country:us/state:il/county:dupage/place:naperville, for cousubs
    url: str

class PipelineContext(BaseModel):
    request_id: str
    jurisdiction_id: str
    name: str # Name of municipality + lsad (ex: Naperville township)
    url: str # Municipality url. Without it we can't scrape anything.
    links: List[Link]  # TODO: move to SEARCH_LINKS
    names: Dict[str, List[str]]  # Canonical names to names found while scraping
    steps: Dict[
        Literal[
            "INIT",
            "SEARCH_LINKS",
            "RESEARCH_MUNICIPALITY",
            "MERGE_RECORDS_WITHIN_LLM",
            "MERGE_RECORDS_ACROSS_LLMS"
        ],
        Union[
            None,
            SearchLinksStep,
            ResearchMunicipalityStep,
            MergeRecordsWithinLLMStep,
            MergeRecordsAcrossLLMsStep
        ]
    ]
    progress: ProgressState

class PipelineCompletePayload(BaseModel):
    pipeline_context: PipelineContext
    people: List[LLMPerson]