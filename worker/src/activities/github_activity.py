import asyncio
import base64
import os
import time
from typing import Optional

import httpx
import jwt
from temporalio import activity

from constants import RunMode

GITHUB_APP_ID = os.environ["GITHUB_APP_ID"]
GITHUB_APP_PRIVATE_KEY_BASE64 = os.environ["GITHUB_APP_PRIVATE_KEY_BASE64"]
GITHUB_APP_INSTALLATION_ID = os.environ["GITHUB_APP_INSTALLATION_ID"]
GITHUB_ORG = os.environ.get("GITHUB_ORG", "CivicPatch")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "server")

_CIVICPATCH_ORG_URL = os.environ.get("CIVICPATCH_ORG_URL", "http://civicpatch-org:80")
_SERVICE_API_KEY = os.environ.get("SERVICE_API_KEY", "")

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


async def _poll_run_id(client: httpx.AsyncClient, request_id: str) -> Optional[int]:
    resp = await client.get(
        f"{_CIVICPATCH_ORG_URL}/api/v1/jobs/{request_id}/run",
        headers={"Authorization": _SERVICE_API_KEY},
    )
    if resp.status_code == 200:
        return resp.json()["run_id"]
    return None


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

    async with httpx.AsyncClient() as client:
        while True:
            activity.heartbeat(f"waiting for run registration: request_id={request_id}")
            run_id = await _poll_run_id(client, request_id)
            if run_id is not None:
                activity.logger.info(f"Found run ID: {run_id}")
                return run_id
            activity.logger.info("Run not registered yet, retrying in 5s...")
            await asyncio.sleep(5)


@activity.defn
async def find_github_run(request_id: str) -> int:
    """Poll until data_scrape.yml registers its run_id for this request_id."""
    async with httpx.AsyncClient() as client:
        while True:
            activity.heartbeat(f"waiting for run registration: request_id={request_id}")
            run_id = await _poll_run_id(client, request_id)
            if run_id is not None:
                activity.logger.info(f"Found run ID: {run_id}")
                return run_id
            activity.logger.info("Run not registered yet, retrying in 5s...")
            await asyncio.sleep(5)


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
