from typing import Any, Literal, Optional

from pydantic import BaseModel


# ──────────────────────────────────────────────
# Request models
# ──────────────────────────────────────────────


class CreatePipelineRunRequest(BaseModel):
    jurisdiction_ocdid: str
    dispatch_mode: Literal["local", "remote"] = "remote"
    name: Optional[str] = None
    url: Optional[str] = None
    source_urls: Optional[list[str]] = None


class BatchPipelineRunRequest(BaseModel):
    state: str
    num_jurisdictions: int = 10


class RegisterGithubRunRequest(BaseModel):
    run_id: int


class UpdatePipelineRunStatusRequest(BaseModel):
    status: str
    progress: Optional[int] = None
    jurisdiction_ocdid: Optional[str] = None
    error_type: Optional[str] = None
    issues: list[dict] = []


class PostPipelineRunResultRequest(BaseModel):
    pull_request_url: Optional[str] = None
    data: Optional[Any] = None


class ResolveUnrecognizedRoleGroupRequest(BaseModel):
    role: str
    request_ids: list[str]


class CreateRegisterRequest(BaseModel):
    request_id: str
    arguments: dict


class PostResultRequest(BaseModel):
    pull_request_url: Optional[str] = None
    data: Optional[Any] = None


# ──────────────────────────────────────────────
# Response models
# ──────────────────────────────────────────────


class UpdatePipelineRunStatusResponse(BaseModel):
    request_id: str
    status: str
    progress: Optional[int] = None


class CreatePipelineRunResponse(BaseModel):
    request_id: str
    status: str


class GetPipelineRunResponse(BaseModel):
    request_id: str
    status: str
    progress: int
    arguments: dict
    result: Optional[Any] = None
    pull_request_url: Optional[str] = None
    created_at: float
    updated_at: float


class GetPipelineRunStatusResponse(BaseModel):
    request_id: str
    status: str
    progress: int


class ErrorResponse(BaseModel):
    error: str
