from fastapi import UploadFile
from pydantic import BaseModel
from typing import Literal, Optional, List

class JurisdictionsByOcdidsRequest(BaseModel):
    ocdids: List[str]

class OdSyncRequestSchema(BaseModel):
    jurisdiction_ocdids: Optional[List[str]] = None

class ServerDetail(BaseModel):
    user_email: str
    server_url: str

class HandleSubmitJobArtifactsRequest(BaseModel):
    zip_path: str
    temp_dir: str
    request_id: str
    jurisdiction_ocdid: str
    server_detail: ServerDetail
    job_status: Optional[str] = None


class ResolveIssueRequest(BaseModel):
    # unrecognized_role fields:
    scope: Optional[Literal["global", "state", "locality"]] = None
    state: Optional[str] = None
    locality: Optional[str] = None
    # dead_url fields:
    new_url: Optional[str] = None
    comment: Optional[str] = None
