"""The activities a scrape runs: dispatch it, watch it, and ask the API what to scrape.

Moved verbatim from the standalone `worker` package on 2026-09-05, when that image folded into
this one. Behaviour is unchanged, including the HTTP hop back to this same service — in-process
these could use `database/` directly, but that is a behaviour change and belongs in its own diff.

The three source modules each had a private `_HEADERS`; merged, GitHub's and the API's had to be
told apart, which is the only rename in the move.
"""

import asyncio
import base64
import json
import os
import time
from typing import Optional

import httpx
import jwt
from temporalio import activity

from lib.temporal.types import RunConclusion
from services.spend_budget import cap_reached_for_state
from shared.utils.statuses import PipelineRunStatus

GITHUB_APP_ID = os.environ["GITHUB_APP_ID"]
GITHUB_APP_PRIVATE_KEY_BASE64 = os.environ["GITHUB_APP_PRIVATE_KEY_BASE64"]
GITHUB_APP_INSTALLATION_ID = os.environ["GITHUB_APP_INSTALLATION_ID"]
GITHUB_ORG = os.environ.get("GITHUB_ORG", "CivicPatch")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "server")

API_URL = os.environ["CIVICPATCH_ORG_URL"]
SERVICE_API_KEY = os.environ["SERVICE_API_KEY"]

_CIVICPATCH_LOCAL_URL = os.environ.get("CIVICPATCH_LOCAL_URL", "http://pipelines:8001")

_GITHUB_API = "https://api.github.com"

_GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
_API_HEADERS = {"Authorization": SERVICE_API_KEY}

_TERMINAL_STATUSES = {PipelineRunStatus.SUCCESS, PipelineRunStatus.ERROR, PipelineRunStatus.CANCELLED}


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
            f"{_GITHUB_API}/app/installations/{GITHUB_APP_INSTALLATION_ID}/access_tokens",
            headers={**_GITHUB_HEADERS, "Authorization": f"Bearer {_generate_jwt()}"},
        )
        resp.raise_for_status()
        return resp.json()["token"]


@activity.defn
async def trigger_github_action(
    jurisdiction_ocdid: str,
    pipeline_run_id: str,
    url: Optional[str] = None,
    source_urls: Optional[list[str]] = None,
) -> None:
    """Dispatch and return. The run id this used to wait for was never read — the caller
    discards the return — so the wait was only a barrier before `poll_pipeline_run_status`,
    which reaches the same place by watching `requests.status`."""
    token = await _get_installation_token()
    # Two-repo contract: these keys are `data_scrape.yml`'s declared inputs in
    # CivicPatch/server. `workflow_dispatch` validates against the workflow on that repo's
    # default branch, so the rename there has to merge before this does.
    inputs: dict = {"jurisdiction_ocdid": jurisdiction_ocdid, "pipeline_run_id": pipeline_run_id}
    if url:
        inputs["url"] = url
    if source_urls:
        inputs["source_urls"] = json.dumps(source_urls)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_GITHUB_API}/repos/{GITHUB_ORG}/{GITHUB_REPO}/actions/workflows/data_scrape.yml/dispatches",
            headers={**_GITHUB_HEADERS, "Authorization": f"Bearer {token}"},
            json={"ref": "main", "inputs": inputs},
        )
        activity.logger.info(f"workflow_dispatch response: {resp.status_code}")
        resp.raise_for_status()


@activity.defn
async def trigger_local(
    jurisdiction_ocdid: str,
    pipeline_run_id: str,
    url: Optional[str] = None,
    source_urls: Optional[list[str]] = None,
) -> None:
    payload = {
        "pipeline_run_id": pipeline_run_id,
        "jurisdiction_ocdid": jurisdiction_ocdid,
        "url": url,
        "source_urls": source_urls,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{_CIVICPATCH_LOCAL_URL}/pipeline_runs", json=payload, timeout=30)
        resp.raise_for_status()
    activity.logger.info(f"Local job triggered: {pipeline_run_id}")


@activity.defn
async def cancel_local_run(pipeline_run_id: str) -> None:
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
                f"{_CIVICPATCH_LOCAL_URL}/pipeline_runs/{pipeline_run_id}/cancel", timeout=15
            )
            resp.raise_for_status()
        activity.logger.info(f"Cancelled local scrape: {pipeline_run_id}")
    except Exception as e:
        activity.logger.warning(f"Could not cancel local scrape {pipeline_run_id}: {e}")


@activity.defn
async def update_pipeline_run_status(pipeline_run_id: str, status: str, progress: Optional[int] = None) -> None:
    async with httpx.AsyncClient(headers=_API_HEADERS, timeout=15) as client:
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
            async with httpx.AsyncClient(headers=_API_HEADERS, timeout=15) as client:
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


@activity.defn
async def claim_scrape_candidates(
    state: str,
    num_jurisdictions: int | None = None,
    created_by_user_id: str | None = None,
) -> list[dict]:
    """The jurisdictions this run will scrape, each with a changeset already registered.

    Asks the API because selecting-and-registering is one operation owned by a service, not
    because HTTP is safer than SQL — this process holds database credentials and a pool, and
    `expiry_activities` uses them. Reimplementing the claim here would duplicate the logic, and
    that is the whole of the argument.

    The claim is atomic because it is one transaction, which is what stops the same jurisdiction
    being handed to two batches.

    Safe to retry: a registered changeset is a non-terminal run, which the candidate query
    excludes — so a second attempt after a partial failure resumes rather than duplicating.
    """
    async with httpx.AsyncClient(headers=_API_HEADERS, timeout=60) as client:
        resp = await client.post(
            f"{API_URL}/api/v1/pipeline_runs/batch/claim",
            json={
                "state": state,
                "num_jurisdictions": num_jurisdictions,
                "created_by_user_id": created_by_user_id,
            },
        )
        resp.raise_for_status()
        return resp.json()["data"]["jurisdictions"]


@activity.defn
async def budget_cap_reached(state: str) -> Optional[str]:
    """Which monthly cap this state has reached, or None if it may keep spending.

    Reads the database rather than calling the API: this is two reads and a pure comparison,
    with no logic a service owns — unlike the claim, where selecting and registering are one
    operation that must not be reimplemented here.

    Returns the name rather than a bool so the caller can say *which* cap stopped it. An
    operator told only "over budget" cannot tell whether to raise one state's cap or the
    global one.
    """
    cap = await cap_reached_for_state(state)
    return cap.value if cap else None
