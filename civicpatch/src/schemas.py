from typing import Dict, List, TypedDict
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
    GENERATE_REPORT = "GENERATE_REPORT"
    SEND_TO_GITHUB = "SEND_TO_GITHUB"
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

class Person(TypedDict):
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