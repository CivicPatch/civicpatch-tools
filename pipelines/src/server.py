import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from pipelines_environment import get_env_vars
from runners.engine import PipelineRunError
from runners.people_collector.main import start_threaded
from runners.people_collector.schemas import PipelineRunConfig
import services.civicpatch_api as civicpatch_api
from services.civicpatch_api import update_pipeline_run_status
from shared.utils.statuses import PipelineRunStatus

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
    url: Optional[str] = None
    source_urls: Optional[list[str]] = None


class PipelineRunStatusResponse(BaseModel):
    request_id: str
    status: str


async def _run(request_id: str, jurisdiction_ocdid: str, url: Optional[str], source_urls: Optional[list[str]]) -> None:
    env = get_env_vars()
    headers = {"Authorization": env["SERVICE_API_KEY"]}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
            config_data = await civicpatch_api.fetch_pipeline_run_config(client, logger, request_id)
        config = PipelineRunConfig(
            url=url or config_data["url"],
            name=config_data.get("name"),
            source_urls=source_urls or config_data.get("source_urls"),
        )
    except Exception:
        logger.exception("job %s failed during config fetch", request_id)
        async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
            await update_pipeline_run_status(client, logger, request_id, jurisdiction_ocdid, PipelineRunStatus.ERROR, 0)
        return

    async def _run_pipeline():
        try:
            await start_threaded(request_id, jurisdiction_ocdid, config)
        except PipelineRunError:
            pass
        except Exception:
            logger.exception("job %s failed", request_id)
            async with httpx.AsyncClient(headers={"Authorization": env["SERVICE_API_KEY"]}, timeout=30.0) as client:
                await update_pipeline_run_status(client, logger, request_id, jurisdiction_ocdid, PipelineRunStatus.ERROR, 0)

    task = asyncio.create_task(_run_pipeline())
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)


@app.post("/pipeline_runs", response_model=PipelineRunStatusResponse)
async def trigger_job(req: TriggerJobRequest) -> PipelineRunStatusResponse:
    task = asyncio.create_task(_run(req.request_id, req.jurisdiction_ocdid, req.url, req.source_urls))
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)
    return PipelineRunStatusResponse(request_id=req.request_id, status=PipelineRunStatus.PENDING)
