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
    pipeline_run_id: str
    status: str


# ── POST /api/v1/pipeline_runs/batch ─────────────────────────────────────────

class BatchPipelineRunRequest(BaseModel):
    state: str
    # None means every eligible jurisdiction — which is what "scrape this state" means. A
    # number is a ceiling, kept for callers that want a smaller bite.
    num_jurisdictions: Optional[int] = None
    # Who asked. Carried through the workflow so the changesets it registers are attributed to
    # the person who pressed the button, not to the system.
    created_by_user_id: Optional[str] = None


# ── POST /api/v1/pipeline_runs/register (internal) ───────────────────────────

class RegisterPipelineRunRequest(BaseModel):
    pipeline_run_id: str
    jurisdiction_ocdid: str
    name: Optional[str] = None
    url: Optional[str] = None


# ── PATCH /api/v1/pipeline_runs/{pipeline_run_id}/status ──────────────────────────

class UpdatePipelineRunStatusRequest(BaseModel):
    status: str
    progress: Optional[int] = None
    jurisdiction_ocdid: Optional[str] = None
    error_type: Optional[str] = None
    error_detail: Optional[dict] = None


class UpdatePipelineRunStatusResponse(BaseModel):
    pipeline_run_id: str
    status: str
    progress: Optional[int] = None


# ── POST /api/v1/pipeline_runs/{pipeline_run_id}/submit (internal) ────────────────

class HandleSubmitPipelineRunArtifactsRequest(BaseModel):
    zip_path: str
    temp_dir: str
    pipeline_run_id: str
    jurisdiction_ocdid: str
    server_detail: ServerDetail
    pipeline_run_status: Optional[str] = None
    env: str = "production"


class SubmitPipelineRunArtifactsResponse(BaseModel):
    status: str
    pipeline_run_id: str
    jurisdiction_ocdid: str


# ── PATCH /api/v1/pipeline_runs/issues/{issue_id}/flag ───────────────────────

class FlagPipelineIssueRequest(BaseModel):
    is_flagged: bool


# ── GET /api/v1/pipeline_runs/{pipeline_run_id} ───────────────────────────────────

# ── GET /api/v1/pipeline_runs/{pipeline_run_id}/status ────────────────────────────

class GetPipelineRunStatusResponse(BaseModel):
    pipeline_run_id: str
    status: str
    progress: int


# ── GET /api/v1/jurisdictions/{ocdid}/pipeline_runs ──────────────────────────

class JurisdictionPipelineRun(BaseModel):
    """One attempt on this jurisdiction, whether or not it proposed anything.

    Every other read reaches a run through `changeset_id`, so a run that minted no changeset —
    the whole population `changeset_summaries` calls "attempts that died proposing nothing" —
    is unreachable. This is the read that asks by jurisdiction instead.
    """

    pipeline_run_id: str
    status: Optional[str]
    progress: Optional[int]
    is_running: bool
    created_at: Optional[str]
    finished_at: Optional[str]
    # The proposal it minted, None if it never reached ingest.
    changeset_id: Optional[str]
    # Why it ended, for a run that filed one. `no_roster_found` is an outcome, not a fault.
    issue_type: Optional[str]


# ── The stale-run sweep (not an endpoint) ────────────────────────────────────

class ExpiredRun(BaseModel):
    """A run the sweep gave up on, and the proposal it had minted — None if it never reached
    ingest. Two fields rather than one id, because the caller needs to tell them apart."""

    pipeline_run_id: str
    changeset_id: Optional[str]
