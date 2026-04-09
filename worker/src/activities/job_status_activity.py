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
    while True:
        activity.heartbeat(f"polling job {request_id}")
        status = None
        try:
            async with httpx.AsyncClient(headers=_HEADERS, timeout=15) as client:
                resp = await client.get(f"{API_URL}/api/v1/jobs/{request_id}/status")
                resp.raise_for_status()
            status = resp.json()["status"]
        except httpx.HTTPStatusError as e:
            if e.response.status_code < 500:
                raise RuntimeError(f"poll_job_status request failed: {type(e).__name__}: {e}") from None
            activity.logger.warning(f"Job {request_id}: server error {e.response.status_code}, will retry")
        except httpx.HTTPError as e:
            activity.logger.warning(f"Job {request_id}: transient error ({type(e).__name__}), will retry")
        if status is not None:
            activity.logger.info(f"Job {request_id}: status={status}")
            if status in _TERMINAL_STATUSES:
                return RunConclusion.SUCCESS if status == JobStatus.COMPLETED else RunConclusion.FAILURE
        try:
            await asyncio.sleep(15)
        except asyncio.CancelledError:
            raise
        activity.heartbeat(f"polling job {request_id}")
