from typing import Any, Literal, Optional

from pydantic import BaseModel


# ──────────────────────────────────────────────
# Request models
# ──────────────────────────────────────────────


class CreateJobRequest(BaseModel):
    jurisdiction_ocdid: str
    dispatch_mode: Literal["local", "remote"] = "remote"
    name: Optional[str] = None
    url: Optional[str] = None
    source_urls: Optional[list[str]] = None


class BatchJobRequest(BaseModel):
    state: str
    num_jurisdictions: int = 10


class RegisterGithubRunRequest(BaseModel):
    run_id: int


class UpdateJobStatusRequest(BaseModel):
    status: str
    progress: Optional[int] = None
    jurisdiction_ocdid: Optional[str] = None


class PostJobResultRequest(BaseModel):
    pull_request_url: Optional[str] = None
    data: Optional[Any] = None


class CreateRegisterRequest(BaseModel):
    request_id: str
    arguments: dict


class PostResultRequest(BaseModel):
    pull_request_url: Optional[str] = None


# ──────────────────────────────────────────────
# Response models
# ──────────────────────────────────────────────


class UpdateJobStatusResponse(BaseModel):
    request_id: str
    status: str
    progress: Optional[int] = None


class CreateJobResponse(BaseModel):
    request_id: str
    status: str


class GetJobResponse(BaseModel):
    request_id: str
    status: str
    progress: int
    arguments: dict
    result: Optional[Any] = None
    pull_request_url: Optional[str] = None
    created_at: float
    updated_at: float


class GetJobStatusResponse(BaseModel):
    request_id: str
    status: str
    progress: int


class ErrorResponse(BaseModel):
    error: str
