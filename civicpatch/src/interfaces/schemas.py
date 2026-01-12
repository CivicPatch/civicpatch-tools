from jobs.people_collector.schemas import WorkflowStatus, WorkflowConfig
from pydantic import BaseModel
from shared.utils import id_utils
from typing import List
from urllib.parse import urlparse

class PeopleCollectorJobRequest(BaseModel):
    jurisdiction_ocdid: str  # Format: ocd-jurisdiction/country:us/state:wa/place:seattle
    # OR ocd-jurisdiction/country:us/state:il/county:dupage/place:naperville, for cousubs
    state: WorkflowStatus = WorkflowStatus.INIT
    config: WorkflowConfig

def validate_people_request(request: PeopleCollectorJobRequest) -> tuple[List[str], List[str]]:
    warnings = []
    errors = []

    jurisdiction_ocdid_obj = id_utils.parse_jurisdiction_ocdid(request.jurisdiction_ocdid)
    if not jurisdiction_ocdid_obj:
        errors.append(f"Invalid jurisdiction_ocdid format: {request.jurisdiction_ocdiddid}.")
    if not request.config.name:
        warnings.append(
            "Missing 'name' field. Substituting with place name from jurisdiction_ocdid."
        )
    if not request.config.url:
        errors.append("Missing 'url' field.")

    # Check all source_urls, if present, are valid URLs
    if request.config.source_urls:
        for url in request.config.source_urls:
            parse_url = urlparse(url)
            if not all([parse_url.scheme, parse_url.netloc]):
                errors.append(f"Invalid URL format: {url}.")
            
    return warnings, errors
