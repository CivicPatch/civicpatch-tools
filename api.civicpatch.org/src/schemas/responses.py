from typing import Optional
from pydantic import BaseModel

class SubmitJobArtifactsResponse(BaseModel):
    filename: str
    status: str
    zip_file_url: Optional[str] = None
    request_id: str
    jurisdiction_ocdid: str