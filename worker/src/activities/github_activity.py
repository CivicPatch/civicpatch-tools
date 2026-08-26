import base64
import json
import os
import time
from typing import Optional

import httpx
import jwt
from temporalio import activity

GITHUB_APP_ID = os.environ["GITHUB_APP_ID"]
GITHUB_APP_PRIVATE_KEY_BASE64 = os.environ["GITHUB_APP_PRIVATE_KEY_BASE64"]
GITHUB_APP_INSTALLATION_ID = os.environ["GITHUB_APP_INSTALLATION_ID"]
GITHUB_ORG = os.environ.get("GITHUB_ORG", "CivicPatch")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "server")

_CIVICPATCH_LOCAL_URL = os.environ.get("CIVICPATCH_LOCAL_URL", "http://pipelines:8001")

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
async def trigger_github_action(
    jurisdiction_ocdid: str,
    request_id: str,
    url: Optional[str] = None,
    source_urls: Optional[list[str]] = None,
) -> None:
    """Dispatch and return. The run id this used to wait for was never read — the caller
    discards the return — so the wait was only a barrier before `poll_pipeline_run_status`,
    which reaches the same place by watching `requests.status`."""
    token = await _get_installation_token()
    inputs: dict = {"jurisdiction_ocdid": jurisdiction_ocdid, "request_id": request_id}
    if url:
        inputs["url"] = url
    if source_urls:
        inputs["source_urls"] = json.dumps(source_urls)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.github.com/repos/{GITHUB_ORG}/{GITHUB_REPO}/actions/workflows/data_scrape.yml/dispatches",
            headers={**_HEADERS, "Authorization": f"Bearer {token}"},
            json={"ref": "main", "inputs": inputs},
        )
        activity.logger.info(f"workflow_dispatch response: {resp.status_code}")
        resp.raise_for_status()


@activity.defn
async def trigger_local(
    jurisdiction_ocdid: str,
    request_id: str,
    url: Optional[str] = None,
    source_urls: Optional[list[str]] = None,
) -> None:
    payload = {
        "request_id": request_id,
        "jurisdiction_ocdid": jurisdiction_ocdid,
        "url": url,
        "source_urls": source_urls,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{_CIVICPATCH_LOCAL_URL}/pipeline_runs", json=payload, timeout=30)
        resp.raise_for_status()
    activity.logger.info(f"Local job triggered: {request_id}")


@activity.defn
async def cancel_local_run(request_id: str) -> None:
    """Stop a scrape running on the local pipelines server.

    Cancelling the workflow stops the poller watching the scrape, not the scrape: it carries on
    and keeps reporting progress, so the run reappears as RUNNING moments later. This is run
    from the workflow's cancellation path so it covers every way a run can be stopped — the UI,
    the Temporal console, an execution timeout — not only the one endpoint.

    Never raises. The cancel has already been decided, and a pipelines server we cannot reach
    must not turn a cancelled workflow into a failed one.
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_CIVICPATCH_LOCAL_URL}/pipeline_runs/{request_id}/cancel", timeout=15
            )
            resp.raise_for_status()
        activity.logger.info(f"Cancelled local scrape: {request_id}")
    except Exception as e:
        activity.logger.warning(f"Could not cancel local scrape {request_id}: {e}")
