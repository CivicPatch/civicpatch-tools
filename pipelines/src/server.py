import asyncio
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from jobs.engine import WorkflowPausedError
from jobs.people_collector.main import start_threaded
from jobs.people_collector.schemas import WorkflowConfig
from shared.utils.statuses import JobStatus

app = FastAPI()

_job_statuses: dict[str, JobStatus] = {}


class TriggerJobRequest(BaseModel):
    request_id: str
    jurisdiction_ocdid: str
    name: Optional[str] = None
    url: str
    source_urls: Optional[list[str]] = None


class JobStatusResponse(BaseModel):
    request_id: str
    status: str


async def _run(request_id: str, jurisdiction_ocdid: str, config: WorkflowConfig) -> None:
    _job_statuses[request_id] = JobStatus.RUNNING
    try:
        await start_threaded(request_id, jurisdiction_ocdid, config)
        _job_statuses[request_id] = JobStatus.COMPLETED
    except WorkflowPausedError:
        _job_statuses[request_id] = JobStatus.PAUSED
    except Exception:
        _job_statuses[request_id] = JobStatus.ERROR


@app.post("/jobs", response_model=JobStatusResponse)
async def trigger_job(req: TriggerJobRequest) -> JobStatusResponse:
    config = WorkflowConfig(url=req.url, name=req.name, source_urls=req.source_urls)
    _job_statuses[req.request_id] = JobStatus.PENDING
    asyncio.create_task(_run(req.request_id, req.jurisdiction_ocdid, config))
    return JobStatusResponse(request_id=req.request_id, status=JobStatus.PENDING)


@app.get("/jobs/{request_id}", response_model=JobStatusResponse)
async def get_job(request_id: str) -> JobStatusResponse:
    status = _job_statuses.get(request_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(request_id=request_id, status=status)
