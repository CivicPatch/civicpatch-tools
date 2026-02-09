from pydantic import BaseModel

class SubmitJobArtifactsResponse(BaseModel):
    filename: str
    status: str
    zip_file_url: str
    request_id: str
    jurisdiction_ocdid: str