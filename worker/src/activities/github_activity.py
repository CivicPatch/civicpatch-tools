import asyncio
import base64
import os
import time
from datetime import datetime, timezone
from typing import Optional

import httpx
import jwt
from temporalio import activity

from constants import RunConclusion, RunMode

GITHUB_APP_ID = os.environ["GITHUB_APP_ID"]
GITHUB_APP_PRIVATE_KEY_BASE64 = os.environ["GITHUB_APP_PRIVATE_KEY_BASE64"]
GITHUB_APP_INSTALLATION_ID = os.environ["GITHUB_APP_INSTALLATION_ID"]
GITHUB_ORG = os.environ.get("GITHUB_ORG", "CivicPatch")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "server")

_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def _generate_jwt() -> str:
    private_key = base64.b64decode(GITHUB_APP_PRIVATE_KEY_BASE64).decode()
    now = int(time.time())
    return jwt.encode(
        {"iat": now - 60, "exp": now + 600, "iss": GITHUB_APP_ID},
        private_key,
        algorithm="RS256",
    )


async def _get_installation_token() -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.github.com/app/installations/{GITHUB_APP_INSTALLATION_ID}/access_tokens",
            headers={**_HEADERS, "Authorization": f"Bearer {_generate_jwt()}"},
        )
        resp.raise_for_status()
        return resp.json()["token"]


@activity.defn
async def trigger_github_action(jurisdiction_ocdid: str, request_id: str, mode: str = RunMode.START) -> int:
    token = await _get_installation_token()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.github.com/repos/{GITHUB_ORG}/{GITHUB_REPO}/actions/workflows/data_scrape.yml/dispatches",
            headers={**_HEADERS, "Authorization": f"Bearer {token}"},
            json={
                "ref": "main",
                "inputs": {
                    "jurisdiction_ocdid": jurisdiction_ocdid,
                    "request_id": request_id,
                    "mode": mode,
                },
            },
        )
        activity.logger.info(f"workflow_dispatch response: {resp.status_code}")
        resp.raise_for_status()
        # workflow_dispatch returns 204 No Content — find our run by matching request_id in step names
        for attempt in range(10):
            await asyncio.sleep(5)
            runs_resp = await client.get(
                f"https://api.github.com/repos/{GITHUB_ORG}/{GITHUB_REPO}/actions/workflows/data_scrape.yml/runs",
                headers={**_HEADERS, "Authorization": f"Bearer {token}"},
                params={"per_page": 10, "event": "workflow_dispatch"},
            )
            runs_resp.raise_for_status()
            for run in runs_resp.json()["workflow_runs"]:
                jobs_resp = await client.get(
                    f"https://api.github.com/repos/{GITHUB_ORG}/{GITHUB_REPO}/actions/runs/{run['id']}/jobs",
                    headers={**_HEADERS, "Authorization": f"Bearer {token}"},
                )
                jobs_resp.raise_for_status()
                for job in jobs_resp.json()["jobs"]:
                    for step in job.get("steps", []):
                        if request_id in step["name"]:
                            activity.logger.info(f"Found run ID: {run['id']}")
                            return run["id"]
            activity.logger.info(f"Run not found yet (attempt {attempt + 1}/10), retrying...")
        raise RuntimeError(f"No run found with request_id={request_id} after 10 attempts")


@activity.defn
async def poll_run_status(run_id: int) -> str:
    """Polls until run reaches a terminal status. Heartbeats to stay alive."""
    token = await _get_installation_token()
    async with httpx.AsyncClient() as client:
        while True:
            activity.heartbeat(f"polling run {run_id}")
            resp = await client.get(
                f"https://api.github.com/repos/{GITHUB_ORG}/{GITHUB_REPO}/actions/runs/{run_id}",
                headers={**_HEADERS, "Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            run = resp.json()
            status = run["status"]
            conclusion = run.get("conclusion")
            activity.logger.info(f"Run {run_id}: status={status} conclusion={conclusion}")

            if status == "completed":
                return conclusion or "unknown"

            try:
                await asyncio.sleep(15)
            except asyncio.CancelledError:
                raise


_CIVICPATCH_LOCAL_URL = os.environ.get("CIVICPATCH_LOCAL_URL", "http://pipelines:8000")


@activity.defn
async def trigger_local_job(
    jurisdiction_ocdid: str,
    request_id: str,
    name: Optional[str],
    url: str,
    source_urls: Optional[list[str]],
) -> None:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_CIVICPATCH_LOCAL_URL}/jobs",
            json={
                "request_id": request_id,
                "jurisdiction_ocdid": jurisdiction_ocdid,
                "name": name,
                "url": url,
                "source_urls": source_urls,
            },
            timeout=10,
        )
        resp.raise_for_status()
        activity.logger.info(f"Local job triggered: {request_id}")


