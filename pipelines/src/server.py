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

# Keyed by pipeline_run_id so a run can be cancelled. Previously an anonymous set: a scrape had no
# handle, so cancelling in the UI stopped the Temporal poller while this kept scraping to
# completion — minutes of work and LLM spend for a run nobody was waiting on.
_running_tasks: dict[str, asyncio.Task] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    if _running_tasks:
        logger.info("Waiting for %d in-flight pipeline run(s) to finish...", len(_running_tasks))
        await asyncio.gather(*_running_tasks.values(), return_exceptions=True)


app = FastAPI(lifespan=lifespan)


def _track(pipeline_run_id: str, task: asyncio.Task) -> None:
    _running_tasks[pipeline_run_id] = task
    task.add_done_callback(lambda _: _running_tasks.pop(pipeline_run_id, None))


class StartPipelineRunRequest(BaseModel):
    pipeline_run_id: str
    jurisdiction_ocdid: str
    url: Optional[str] = None
    source_urls: Optional[list[str]] = None


class PipelineRunStatusResponse(BaseModel):
    pipeline_run_id: str
    status: str


async def _run(pipeline_run_id: str, jurisdiction_ocdid: str, url: Optional[str], source_urls: Optional[list[str]]) -> None:
    env = get_env_vars()
    headers = {"Authorization": env["SERVICE_API_KEY"]}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
            config_data = await civicpatch_api.fetch_pipeline_run_config(client, logger, pipeline_run_id)
        config = PipelineRunConfig(
            url=url or config_data["url"],
            name=config_data.get("name"),
            source_urls=source_urls or config_data.get("source_urls"),
        )
    except Exception:
        logger.exception("pipeline run %s failed during config fetch", pipeline_run_id)
        async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
            await update_pipeline_run_status(client, logger, pipeline_run_id, jurisdiction_ocdid, PipelineRunStatus.ERROR, 0)
        return

    async def _run_pipeline():
        try:
            await start_threaded(pipeline_run_id, jurisdiction_ocdid, config)
        except PipelineRunError:
            pass
        except Exception:
            logger.exception("pipeline run %s failed", pipeline_run_id)
            async with httpx.AsyncClient(headers={"Authorization": env["SERVICE_API_KEY"]}, timeout=30.0) as client:
                await update_pipeline_run_status(client, logger, pipeline_run_id, jurisdiction_ocdid, PipelineRunStatus.ERROR, 0)

    _track(pipeline_run_id, asyncio.create_task(_run_pipeline()))


@app.post("/pipeline_runs", response_model=PipelineRunStatusResponse)
async def start_pipeline_run(req: StartPipelineRunRequest) -> PipelineRunStatusResponse:
    _track(req.pipeline_run_id, asyncio.create_task(
        _run(req.pipeline_run_id, req.jurisdiction_ocdid, req.url, req.source_urls)
    ))
    return PipelineRunStatusResponse(pipeline_run_id=req.pipeline_run_id, status=PipelineRunStatus.PENDING)


@app.post("/pipeline_runs/{pipeline_run_id}/cancel", response_model=PipelineRunStatusResponse)
async def cancel_pipeline_run(pipeline_run_id: str) -> PipelineRunStatusResponse:
    """Stop a running scrape. Idempotent: a run that already finished, or was never started
    here, reports cancelled rather than 404 — the caller wants it stopped, and it is."""
    task = _running_tasks.get(pipeline_run_id)
    if task and not task.done():
        task.cancel()
        logger.info("Cancelled in-flight pipeline run %s", pipeline_run_id)
    return PipelineRunStatusResponse(pipeline_run_id=pipeline_run_id, status=PipelineRunStatus.CANCELLED)
