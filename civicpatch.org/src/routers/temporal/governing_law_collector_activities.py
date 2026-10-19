"""The governing_law_collector's own activities: its doors and its batch's questions. Watching a
run, updating its status and cancelling a local one are the scrape's, reused as they are."""

from typing import Optional

import httpx
from temporalio import activity

from routers.temporal.pipeline_run_activities import (
    API_URL,
    GITHUB_ORG,
    GITHUB_REPO,
    _API_HEADERS,
    _CIVICPATCH_LOCAL_URL,
    _GITHUB_API,
    _GITHUB_HEADERS,
    _get_installation_token,
)

# Its doors: the pipelines server's route, and the Actions workflow in CivicPatch/server whose
# inputs are this run's (jurisdiction_ocdid, pipeline_run_id). Two-repo contract, like the scrape's.
LOCAL_PATH = "/pipeline_runs/governing_law_collector"
GITHUB_WORKFLOW = "data_collect_governing_law.yml"


@activity.defn
async def trigger_governing_law_collector_local(jurisdiction_ocdid: str, pipeline_run_id: str) -> None:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_CIVICPATCH_LOCAL_URL}{LOCAL_PATH}",
            json={"pipeline_run_id": pipeline_run_id, "jurisdiction_ocdid": jurisdiction_ocdid},
            timeout=30,
        )
        resp.raise_for_status()
    activity.logger.info(f"Local governing law collection triggered: {pipeline_run_id}")


@activity.defn
async def trigger_governing_law_collector_remote(jurisdiction_ocdid: str, pipeline_run_id: str) -> None:
    token = await _get_installation_token()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_GITHUB_API}/repos/{GITHUB_ORG}/{GITHUB_REPO}/actions/workflows/{GITHUB_WORKFLOW}/dispatches",
            headers={**_GITHUB_HEADERS, "Authorization": f"Bearer {token}"},
            json={"ref": "main", "inputs": {"jurisdiction_ocdid": jurisdiction_ocdid, "pipeline_run_id": pipeline_run_id}},
        )
        activity.logger.info(f"workflow_dispatch response: {resp.status_code}")
        resp.raise_for_status()


@activity.defn
async def claim_jurisdictions_for_governing_law_collector(
    state: str, num_jurisdictions: Optional[int] = None, created_by_user_id: Optional[str] = None
) -> list[dict]:
    """The state's next jurisdictions to collect, each with a run registered, from the API (this
    queue's worker opens no database connection)."""
    async with httpx.AsyncClient(headers=_API_HEADERS, timeout=60) as client:
        resp = await client.post(
            f"{API_URL}/api/v1/pipeline_runs/governing_law_collector/claim",
            json={"state": state, "num_jurisdictions": num_jurisdictions, "created_by_user_id": created_by_user_id},
        )
        resp.raise_for_status()
        return resp.json()["data"]["jurisdictions"]


@activity.defn
async def governing_law_collector_month_cap_reached() -> Optional[str]:
    """Which cap was reached, as `people_collector_month_cap_reached` answers; only ever its month."""
    async with httpx.AsyncClient(headers=_API_HEADERS, timeout=15) as client:
        resp = await client.get(f"{API_URL}/api/v1/pipeline_runs/governing_law_collector/budget_cap")
        resp.raise_for_status()
        return resp.json()["data"]["cap"]
