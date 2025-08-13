from typing import Dict, List, TypedDict, Optional, TypeAlias, Any, Callable
from pydantic import BaseModel
from enum import Enum

class SearchEngineStatus(Enum):
    NOT_STARTED = "not_started"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"

class SearchEngineState(TypedDict):
    status: str # SearchEngineStatus value 

class ProgressState(TypedDict):
    required_data: int
    current_data: int

class LinkStatus(Enum):
    PENDING = "pending"
    SCRAPED = "scraped"
    PREPROCESSED = "preprocessed"
    DONE = "done"
    FAILED = "failed"

class Link(TypedDict):
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
    SEND_TO_GITHUB = "SEND_TO_GITHUB"
    CLEANUP = "CLEANUP"
    RETRY = "RETRY"
    DONE = "DONE"

class PipelineContext(TypedDict):
    state: str
    geoid: str
    search_engines: Dict[str, SearchEngineState]
    links: List[Link] # TODO: move to SEARCH_LINKS
    steps: Dict[str, Dict] # PipelineStatus value
    data: Dict[str, Dict]
    progress: ProgressState

class LLMDataPoint(BaseModel):
    data: Optional[str] = None
    llm_confidence: float
    llm_confidence_reason: str

class LLMPerson(BaseModel):
    name: str
    roles: List[LLMDataPoint]
    divisions: List[LLMDataPoint]
    phone_number: LLMDataPoint
    email: LLMDataPoint 
    website: LLMDataPoint
    start_date: LLMDataPoint 
    end_date: LLMDataPoint 

class PeopleArrayLLMResponseSchema(BaseModel):
    people: List[LLMPerson]
    thought: str

class ProcessedLLMPeople(BaseModel):
    names: List[str]
    records: List[LLMPerson]

class Person(BaseModel):
    name: str
    roles: List[str]
    divisions: List[str]
    image: str
    cdn_image: str
    email: str
    phone_number: str
    website: str
    start_date: str
    end_date: str
    sources: List[str]
    updated_at: str

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

PeopleByNameDict: TypeAlias = Dict[str, ProcessedLLMPeople]
LLMResponsesDict: TypeAlias = Dict[str, List[LLMPerson]]
ProcessedDataDict: TypeAlias = Dict[str, PeopleByNameDict]