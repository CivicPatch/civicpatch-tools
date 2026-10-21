"""The collectors' own activities, each taking the run's kind: its doors and its batch's questions.
Watching a run, updating its status and cancelling a local one are the scrape's, reused as they are."""

from typing import Optional

import httpx
from shared.utils.statuses import PipelineRunKind
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

# The Actions workflow in CivicPatch/server whose inputs are a run's (jurisdiction_ocdid,
# pipeline_run_id): a two-repo contract, like the scrape's, so named here and not derived.
GITHUB_WORKFLOWS = {
    PipelineRunKind.GOVERNING_LAW_COLLECTOR: "data_collect_governing_law.yml",
    PipelineRunKind.ORGANIZATIONS_COLLECTOR: "data_collect_organizations.yml",
}


def local_path(kind: str) -> str:
    """The pipelines server's door for this kind: `server.py` names its routes the same way."""
    return f"/pipeline_runs/{kind}"


@activity.defn
async def trigger_collector_local(kind: str, jurisdiction_ocdid: str, pipeline_run_id: str) -> None:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_CIVICPATCH_LOCAL_URL}{local_path(kind)}",
            json={"pipeline_run_id": pipeline_run_id, "jurisdiction_ocdid": jurisdiction_ocdid},
            timeout=30,
        )
        resp.raise_for_status()
    activity.logger.info(f"Local {kind} run triggered: {pipeline_run_id}")


@activity.defn
async def trigger_collector_remote(kind: str, jurisdiction_ocdid: str, pipeline_run_id: str) -> None:
    github_workflow = GITHUB_WORKFLOWS[PipelineRunKind(kind)]
    token = await _get_installation_token()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_GITHUB_API}/repos/{GITHUB_ORG}/{GITHUB_REPO}/actions/workflows/{github_workflow}/dispatches",
            headers={**_GITHUB_HEADERS, "Authorization": f"Bearer {token}"},
            json={"ref": "main", "inputs": {"jurisdiction_ocdid": jurisdiction_ocdid, "pipeline_run_id": pipeline_run_id}},
        )
        activity.logger.info(f"workflow_dispatch response: {resp.status_code}")
        resp.raise_for_status()


@activity.defn
async def claim_jurisdictions_for_collector(
    kind: str, state: str, num_jurisdictions: Optional[int] = None, created_by_user_id: Optional[str] = None
) -> list[dict]:
    """The state's next jurisdictions to collect, each with a run registered, from the API (this
    queue's worker opens no database connection)."""
    async with httpx.AsyncClient(headers=_API_HEADERS, timeout=60) as client:
        resp = await client.post(
            f"{API_URL}/api/v1/pipeline_runs/{kind}/claim",
            json={"state": state, "num_jurisdictions": num_jurisdictions, "created_by_user_id": created_by_user_id},
        )
        resp.raise_for_status()
        return resp.json()["data"]["jurisdictions"]


@activity.defn
async def collector_month_cap_reached(kind: str) -> Optional[str]:
    """Which cap was reached, as `people_collector_month_cap_reached` answers; only ever its month."""
    async with httpx.AsyncClient(headers=_API_HEADERS, timeout=15) as client:
        resp = await client.get(f"{API_URL}/api/v1/pipeline_runs/{kind}/budget_cap")
        resp.raise_for_status()
        return resp.json()["data"]["cap"]
