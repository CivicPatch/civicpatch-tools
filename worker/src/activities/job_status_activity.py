import asyncio
import os
from typing import Optional

import httpx
from temporalio import activity

from constants import RunConclusion
from shared.utils.statuses import JobStatus

API_URL = os.environ["CIVICPATCH_ORG_URL"]
SERVICE_API_KEY = os.environ["SERVICE_API_KEY"]

_HEADERS = {"Authorization": SERVICE_API_KEY}

_TERMINAL_STATUSES = {JobStatus.COMPLETED, JobStatus.ERROR, JobStatus.PAUSED}


@activity.defn
async def update_job_status(request_id: str, status: str, progress: Optional[int] = None) -> None:
    async with httpx.AsyncClient(headers=_HEADERS, timeout=15) as client:
        resp = await client.patch(
            f"{API_URL}/api/v1/jobs/{request_id}/status",
            json={"status": status, "progress": progress},
        )
        resp.raise_for_status()


@activity.defn
async def poll_job_status(request_id: str) -> str:
    async with httpx.AsyncClient(headers=_HEADERS, timeout=15) as client:
        while True:
            activity.heartbeat(f"polling job {request_id}")
            try:
                resp = await client.get(f"{API_URL}/api/v1/jobs/{request_id}/status")
                resp.raise_for_status()
            except httpx.HTTPError as e:
                raise RuntimeError(f"poll_job_status request failed: {type(e).__name__}: {e}") from None
            status = resp.json()["status"]
            activity.logger.info(f"Job {request_id}: status={status}")
            if status in _TERMINAL_STATUSES:
                return RunConclusion.SUCCESS if status == JobStatus.COMPLETED else RunConclusion.FAILURE
            await asyncio.sleep(15)
            activity.heartbeat(f"polling job {request_id}")
