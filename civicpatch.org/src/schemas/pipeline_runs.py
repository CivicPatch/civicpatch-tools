from typing import Any, List, Literal, Optional

from pydantic import BaseModel


# ── Shared ────────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    error: str


class ServerDetail(BaseModel):
    user_email: str


# ── POST /api/v1/pipeline_runs ────────────────────────────────────────────────

class CreatePipelineRunRequest(BaseModel):
    jurisdiction_ocdid: str
    dispatch_mode: Literal["local", "remote"] = "remote"
    name: Optional[str] = None
    url: Optional[str] = None
    source_urls: Optional[list[str]] = None


class CreatePipelineRunResponse(BaseModel):
    request_id: str
    status: str


# ── POST /api/v1/pipeline_runs/batch ─────────────────────────────────────────

class BatchPipelineRunRequest(BaseModel):
    state: str
    num_jurisdictions: int = 10


# ── POST /api/v1/pipeline_runs/register (internal) ───────────────────────────

class RegisterPipelineRunRequest(BaseModel):
    request_id: str
    jurisdiction_ocdid: str
    name: Optional[str] = None
    url: Optional[str] = None


# ── POST /api/v1/pipeline_runs/{request_id}/run (internal) ───────────────────

class RegisterGithubRunRequest(BaseModel):
    run_id: int


# ── PATCH /api/v1/pipeline_runs/{request_id}/status ──────────────────────────

class UpdatePipelineRunStatusRequest(BaseModel):
    status: str
    progress: Optional[int] = None
    jurisdiction_ocdid: Optional[str] = None
    error_type: Optional[str] = None
    issues: list[dict] = []


class UpdatePipelineRunStatusResponse(BaseModel):
    request_id: str
    status: str
    progress: Optional[int] = None


# ── POST /api/v1/pipeline_runs/{request_id}/result (internal) ────────────────

class PostPipelineRunResultRequest(BaseModel):
    pull_request_url: Optional[str] = None
    data: Optional[Any] = None


# ── POST /api/v1/pipeline_runs/{request_id}/submit (internal) ────────────────

class HandleSubmitPipelineRunArtifactsRequest(BaseModel):
    zip_path: str
    temp_dir: str
    request_id: str
    jurisdiction_ocdid: str
    server_detail: ServerDetail
    pipeline_run_status: Optional[str] = None
    env: str = "production"


class SubmitPipelineRunArtifactsResponse(BaseModel):
    filename: str
    status: str
    zip_file_url: Optional[str] = None
    request_id: str
    jurisdiction_ocdid: str


# ── POST /api/v1/pipeline_runs/issues/{issue_id}/resolve ─────────────────────

class ResolveIssueRequest(BaseModel):
    scope: Optional[Literal["global", "state", "locality"]] = None
    state: Optional[str] = None
    locality: Optional[str] = None


# ── POST /api/v1/pipeline_runs/issues/roles/resolve ──────────────────────────

class ResolveUnrecognizedRoleGroupRequest(BaseModel):
    role: str
    request_ids: list[str]


# ── GET /api/v1/pipeline_runs/{request_id} ───────────────────────────────────

class GetPipelineRunResponse(BaseModel):
    request_id: str
    status: str
    progress: int
    arguments: dict
    result: Optional[Any] = None
    pull_request_url: Optional[str] = None
    created_at: float
    updated_at: float


# ── GET /api/v1/pipeline_runs/{request_id}/status ────────────────────────────

class GetPipelineRunStatusResponse(BaseModel):
    request_id: str
    status: str
    progress: int


# ── POST /api/v1/requests/register (internal) ────────────────────────────────

class CreateRegisterRequest(BaseModel):
    request_id: str
    arguments: dict


# ── POST /api/v1/requests/result (internal) ──────────────────────────────────

class PostResultRequest(BaseModel):
    pull_request_url: Optional[str] = None
    data: Optional[Any] = None
