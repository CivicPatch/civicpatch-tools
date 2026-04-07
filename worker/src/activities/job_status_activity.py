import os
from typing import Optional

import httpx
from temporalio import activity

API_URL = os.environ["API_CIVICPATCH_ORG_URL"]
SERVICE_API_KEY = os.environ["SERVICE_API_KEY"]

_HEADERS = {"Authorization": SERVICE_API_KEY}


@activity.defn
async def update_job_status(request_id: str, status: str, progress: Optional[int] = None) -> None:
    async with httpx.AsyncClient(headers=_HEADERS, timeout=15) as client:
        resp = await client.patch(
            f"{API_URL}/api/v1/jobs/{request_id}/status",
            json={"status": status, "progress": progress},
        )
        resp.raise_for_status()
