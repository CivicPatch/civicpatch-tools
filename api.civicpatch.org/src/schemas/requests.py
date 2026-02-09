from fastapi import UploadFile
from pydantic import BaseModel
from typing import Tuple

class ServerDetail(BaseModel):
    user_email: str
    server_url: str

class HandleSubmitJobArtifactsRequest(BaseModel):
    file: UploadFile
    request_id: str
    jurisdiction_ocdid: str
    server_detail: ServerDetail