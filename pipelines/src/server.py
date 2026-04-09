import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from jobs.engine import WorkflowPausedError
from jobs.people_collector.main import start_threaded
from jobs.people_collector.schemas import WorkflowConfig
from services.civicpatch_api import update_job_status
from shared.utils.statuses import JobStatus

logger = logging.getLogger(__name__)

_running_tasks: set[asyncio.Task] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    if _running_tasks:
        logger.info("Waiting for %d in-flight job(s) to finish...", len(_running_tasks))
        await asyncio.gather(*_running_tasks, return_exceptions=True)


app = FastAPI(lifespan=lifespan)


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
    try:
        await start_threaded(request_id, jurisdiction_ocdid, config)
    except WorkflowPausedError:
        logger.info("job %s paused", request_id)
    except Exception:
        logger.exception("job %s failed", request_id)
        await update_job_status(logger, request_id, jurisdiction_ocdid, JobStatus.ERROR, 0)


@app.post("/jobs", response_model=JobStatusResponse)
async def trigger_job(req: TriggerJobRequest) -> JobStatusResponse:
    config = WorkflowConfig(url=req.url, name=req.name, source_urls=req.source_urls)
    task = asyncio.create_task(_run(req.request_id, req.jurisdiction_ocdid, config))
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)
    return JobStatusResponse(request_id=req.request_id, status=JobStatus.PENDING)
