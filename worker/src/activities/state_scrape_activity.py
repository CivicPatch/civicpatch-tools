"""What a state scrape asks the API for: the jurisdictions it should run against.

The worker owns no database connection, so this asks the API — which is also what makes the
claim atomic: selecting and registering happen in one call, so the same jurisdiction cannot be
handed to two batches.
"""

import os

import httpx
from temporalio import activity

API_URL = os.environ["CIVICPATCH_ORG_URL"]
SERVICE_API_KEY = os.environ["SERVICE_API_KEY"]

_HEADERS = {"Authorization": SERVICE_API_KEY}


@activity.defn
async def claim_scrape_candidates(
    state: str,
    num_jurisdictions: int | None = None,
    created_by_user_id: str | None = None,
) -> list[dict]:
    """The jurisdictions this run will scrape, each with a changeset already registered.

    Safe to retry: a registered changeset is a non-terminal run, which the candidate query
    excludes — so a second attempt after a partial failure resumes rather than duplicating.
    """
    async with httpx.AsyncClient(headers=_HEADERS, timeout=60) as client:
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
