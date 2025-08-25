from typing import Dict, List, Optional, TypeAlias, Any, Callable, Union
from pydantic import BaseModel
from enum import Enum

class SearchEngineStatus(Enum):
    NOT_STARTED = "not_started"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"

class SearchEngineState(BaseModel):
    status: str # SearchEngineStatus value 

class ProgressState(BaseModel):
    required_data: int
    current_data: int

class LinkStatus(Enum):
    PENDING = "pending"
    SCRAPED = "scraped"
    PREPROCESSED = "preprocessed"
    DONE = "done"
    FAILED = "failed"

class Link(BaseModel):
    url: str
    status: str # LinkStatus value
    folder_name: str = ""

class PipelineStatus(Enum):
    INIT = "INIT"
    RESEARCH_MUNICIPALITY = "RESEARCH_MUNICIPALITY"
    SEARCH_LINKS = "SEARCH_LINKS"
    SCRAPE_PAGE = "SCRAPE_PAGE"
    PREPROCESS_PAGE_CONTENT = "PREPROCESS_PAGE_CONTENT"
    PROCESS_PAGE_CONTENT = "PROCESS_PAGE_CONTENT"
    MERGE_RECORDS_WITHIN_SOURCE = "MERGE_RECORDS_WITHIN_SOURCE"
    MERGE_RECORDS_ACROSS_SOURCES = "MERGE_RECORDS_ACROSS_SOURCES"
    MAYBE_SEND_TO_GITHUB = "MAYBE_SEND_TO_GITHUB"
    CLEANUP = "CLEANUP"
    RETRY = "RETRY"
    DONE = "DONE"

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
    # data_sources: List[str] # List of URLs where information was founda

class PeopleArrayLLMResponseSchema(BaseModel):
    people: List[RawLLMPerson]
    thought: str

class Person(RawLLMPerson):
    state: str = ""
    place: str = ""
    cdn_image: str
    data_sources: List[str] # List of source URLs where information was found
    updated_at: str

OtherNamesByCanonicalName: TypeAlias = Dict[str, List[str]] # Canonical name to other names found while scraping
PeopleByName: TypeAlias = Dict[str, List[LLMPerson]]
RecordsBySource: TypeAlias = Dict[str, PeopleByName]

class ProcessPageContentStep(BaseModel):
    records_by_source: RecordsBySource

class MergeRecordsWithinSourceStep(BaseModel):
    people_by_source: Dict[str, List[Person]] # LLM Names to list of Person records

class Disagreement(BaseModel):
    source: str
    person_name: str
    field: str
    value: str

class MissingPerson(BaseModel):
    source: str
    person_name: str

class MergeRecordsAcrossSourcesStep(BaseModel):
    people: List[Person]
    agreement_score: float
    disagreements: List[Disagreement] = []  # List of disagreements found during merging
    missing_people: List[MissingPerson] = []  # List of people missing from some sources

class PipelineContext(BaseModel):
    state: str
    geoid: str
    search_engines: Dict[str, SearchEngineState]
    links: List[Link]  # TODO: move to SEARCH_LINKS
    names: Dict[str, List[str]]  # Canonical names to names found while scraping
    steps: Dict[str, Union[
        MergeRecordsWithinSourceStep,
        MergeRecordsAcrossSourcesStep,
        Any  # Add other step types as needed
    ]]
    data: Dict[str, Union[
        ProcessPageContentStep,
        MergeRecordsWithinSourceStep,
        MergeRecordsAcrossSourcesStep,
        Any
    ]]
    progress: ProgressState

def pydantic_to_dict(obj):
    """
    Recursively convert arbitrarily nested Pydantic models, lists, and dicts to plain dicts/lists.
    """
    if isinstance(obj, list):
        return [pydantic_to_dict(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: pydantic_to_dict(v) for k, v in obj.items()}
    elif hasattr(obj, "model_dump"):  # Pydantic v2
        return obj.model_dump()
    else:
        return obj
    
def dict_to_pydantic(data: Any, constructor: Callable) -> Any:
    """
    Recursively convert arbitrarily nested dicts/lists to Pydantic models using the provided constructor.
    - data: The input data (dict, list, or primitive)
    - constructor: The Pydantic model class or a function to construct the object at this level
    """
    if isinstance(data, list):
        return [dict_to_pydantic(item, constructor) for item in data]
    elif isinstance(data, dict):
        try:
            # Try to construct a model at this level
            return constructor.model_validate(data)
        except Exception:
            # If it fails, try to recursively apply to values (for nested dicts)
            return {k: dict_to_pydantic(v, constructor) for k, v in data.items()}
    else:
        return data

# PeopleByNameDict: TypeAlias = Dict[str, ProcessedLLMPeople]
# ProcessedDataDict: TypeAlias = Dict[str, PeopleByNameDict]

class PipelineCompletePayload(BaseModel):
    pipeline_context: PipelineContext
    people: List[LLMPerson]