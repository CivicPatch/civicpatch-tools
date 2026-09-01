from typing import Optional

from pydantic import BaseModel


# ── Shared ────────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    error: str


class ServerDetail(BaseModel):
    user_email: str


# ── POST /api/v1/pipeline_runs ────────────────────────────────────────────────

class CreatePipelineRunRequest(BaseModel):
    jurisdiction_ocdid: str
    name: Optional[str] = None
    url: Optional[str] = None
    source_urls: Optional[list[str]] = None


class CreatePipelineRunResponse(BaseModel):
    changeset_id: str
    status: str


# ── POST /api/v1/pipeline_runs/batch ─────────────────────────────────────────

class BatchPipelineRunRequest(BaseModel):
    state: str
    num_jurisdictions: int = 10


# ── POST /api/v1/pipeline_runs/register (internal) ───────────────────────────

class RegisterPipelineRunRequest(BaseModel):
    changeset_id: str
    jurisdiction_ocdid: str
    name: Optional[str] = None
    url: Optional[str] = None


# ── PATCH /api/v1/pipeline_runs/{changeset_id}/status ──────────────────────────

class UpdatePipelineRunStatusRequest(BaseModel):
    status: str
    progress: Optional[int] = None
    jurisdiction_ocdid: Optional[str] = None
    error_type: Optional[str] = None
    error_detail: Optional[dict] = None


class UpdatePipelineRunStatusResponse(BaseModel):
    changeset_id: str
    status: str
    progress: Optional[int] = None


# ── POST /api/v1/pipeline_runs/{changeset_id}/submit (internal) ────────────────

class HandleSubmitPipelineRunArtifactsRequest(BaseModel):
    zip_path: str
    temp_dir: str
    changeset_id: str
    jurisdiction_ocdid: str
    server_detail: ServerDetail
    pipeline_run_status: Optional[str] = None
    env: str = "production"


class SubmitPipelineRunArtifactsResponse(BaseModel):
    status: str
    changeset_id: str
    jurisdiction_ocdid: str


# ── PATCH /api/v1/pipeline_runs/issues/{issue_id}/flag ───────────────────────

class FlagPipelineIssueRequest(BaseModel):
    is_flagged: bool


# ── GET /api/v1/pipeline_runs/{changeset_id} ───────────────────────────────────

# ── GET /api/v1/pipeline_runs/{changeset_id}/status ────────────────────────────

class GetPipelineRunStatusResponse(BaseModel):
    changeset_id: str
    status: str
    progress: int


# ── POST /api/v1/requests/register (internal) ────────────────────────────────

class CreateRegisterRequest(BaseModel):
    changeset_id: str
    arguments: dict


# ── POST /api/v1/requests/result (internal) ──────────────────────────────────

class PostResultRequest(BaseModel):
    pull_request_url: Optional[str] = None
