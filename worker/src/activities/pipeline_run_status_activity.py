import asyncio
import os
from typing import Optional

import httpx
from temporalio import activity

from constants import RunConclusion
from shared.utils.statuses import PipelineRunStatus

API_URL = os.environ["CIVICPATCH_ORG_URL"]
SERVICE_API_KEY = os.environ["SERVICE_API_KEY"]

_HEADERS = {"Authorization": SERVICE_API_KEY}

_TERMINAL_STATUSES = {PipelineRunStatus.SUCCESS, PipelineRunStatus.ERROR, PipelineRunStatus.CANCELLED}


@activity.defn
async def update_pipeline_run_status(pipeline_run_id: str, status: str, progress: Optional[int] = None) -> None:
    async with httpx.AsyncClient(headers=_HEADERS, timeout=15) as client:
        resp = await client.patch(
            f"{API_URL}/api/v1/pipeline_runs/{pipeline_run_id}/status",
            json={"status": status, "progress": progress},
        )
        resp.raise_for_status()


@activity.defn
async def poll_pipeline_run_status(pipeline_run_id: str) -> str:
    while True:
        activity.heartbeat(f"polling pipeline run {pipeline_run_id}")
        status = None
        try:
            async with httpx.AsyncClient(headers=_HEADERS, timeout=15) as client:
                resp = await client.get(f"{API_URL}/api/v1/pipeline_runs/{pipeline_run_id}/status")
                resp.raise_for_status()
            status = resp.json()["status"]
        except httpx.HTTPStatusError as e:
            if e.response.status_code < 500:
                raise RuntimeError(f"poll_pipeline_run_status request failed: {type(e).__name__}: {e}") from None
            activity.logger.warning(f"Pipeline run {pipeline_run_id}: server error {e.response.status_code}, will retry")
        except httpx.HTTPError as e:
            activity.logger.warning(f"Pipeline run {pipeline_run_id}: transient error ({type(e).__name__}), will retry")
        if status is not None:
            activity.logger.info(f"Pipeline run {pipeline_run_id}: status={status}")
            if status in _TERMINAL_STATUSES:
                return RunConclusion.SUCCESS if status == PipelineRunStatus.SUCCESS else RunConclusion.FAILURE
        try:
            await asyncio.sleep(15)
        except asyncio.CancelledError:
            raise
        activity.heartbeat(f"polling pipeline run {pipeline_run_id}")
