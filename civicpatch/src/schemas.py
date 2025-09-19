from typing import Dict, List, Optional, TypeAlias, Any, Callable, Union, NamedTuple
from pydantic import BaseModel
from enum import Enum

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

class MunicipalityEntry(BaseModel):
    name: str
    geoid: str
    website: Optional[str] = None
    counties: List[str] = None
    type: str
    government_type: str

class MunicipalityContext(BaseModel):
    state: str
    geoid: str
    municipality_entry: MunicipalityEntry

class RawLLMPerson(BaseModel):
    name: str
    image: Optional[str] = None
    roles: List[str]
    divisions: List[str]
    phone_number: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class LLMPerson(RawLLMPerson):
    data_source: str
    # todo: image
    # sources: List[str] # List of URLs where information was founda

class PeopleArrayLLMResponseSchema(BaseModel):
    people: List[RawLLMPerson]
    thought: str

class Person(RawLLMPerson):
    state: str = ""
    place: str = ""
    counties: List[str] = []
    sources: List[str] # List of source URLs where information was found
    cdn_image: str
    updated_at: str

OtherNamesByCanonicalName: TypeAlias = Dict[str, List[str]] # Canonical name to other names found while scraping
PeopleByName: TypeAlias = Dict[str, List[LLMPerson]]
RecordsBySource: TypeAlias = Dict[str, PeopleByName]

class SearchLinksStep(BaseModel):
    search_engines: Dict[str, SearchEngineState]  # e.g., "google": SearchEngineState
    links: List[Link]

class ProcessPageContentStep(BaseModel):
    records_by_llm: RecordsBySource

class MergeRecordsWithinLLMStep(BaseModel):
    people_by_llm: Dict[str, List[Person]] # LLM Names to list of Person records

class FieldComparison(BaseModel):
    field: str
    merged_value: str
    source_values: Dict[str, str]
    disagreement_score: float

class PersonDisagreements(BaseModel):
    person_name: str
    disagreements: List[FieldComparison]

class MissingPerson(BaseModel):
    name: str
    missing_from_sources: List[str]  # List of source names where this person was not found
    found_in_sources: List[str]  # List of source names where this person was found

class MergeRecordsAcrossLLMsStep(BaseModel):
    people: List[Person]
    agreement_score: float
    disagreements: Dict[str, List[FieldComparison]] = {}
    missing_people: List[MissingPerson] = []  # Now properly typed with MissingPerson class
    validation_issues: List[str] = []

class PipelineContext(BaseModel):
    state: str
    geoid: str
    request_id: str
    links: List[Link]  # TODO: move to SEARCH_LINKS
    names: Dict[str, List[str]]  # Canonical names to names found while scraping
    steps: Dict[str, Union[
        SearchLinksStep,
        MergeRecordsWithinLLMStep,
        MergeRecordsAcrossLLMsStep,
        Any  # Add other step types as needed
    ]]
    progress: ProgressState

# PeopleByNameDict: TypeAlias = Dict[str, ProcessedLLMPeople]
# ProcessedDataDict: TypeAlias = Dict[str, PeopleByNameDict]

class PipelineCompletePayload(BaseModel):
    pipeline_context: PipelineContext
    people: List[LLMPerson]