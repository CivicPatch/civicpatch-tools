import os
from typing import List, Optional

import httpx
from fastapi import Request
from pipelines_environment import get_env_vars
from shared.schemas import GoverningLawOrganizations, JurisdictionExtras, KnownOrganization, LLMCall
from shared.utils.config_utils import (
    RoleConfig,
)
from utils.request_utils import with_retry

SERVER_SOURCE = os.getenv("CIVICPATCH_SERVER_SOURCE")


def _get_cookies(request: Optional[Request]):
    return request.cookies if request else None


def can_scrape_locally() -> bool:
    env = get_env_vars()
    return bool(env.get("GOOGLE_GEMINI_TOKEN") and env.get("TOGETHER_AI_TOKEN"))


async def get_jurisdiction(jurisdiction_ocdid: str, request: Request) -> dict:
    env = get_env_vars()
    params = {"jurisdiction_ocdid": jurisdiction_ocdid, "with_geom": "true"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{env['CIVICPATCH_ORG_URL']}/api/v1/jurisdictions",
            params=params,
            cookies=_get_cookies(request),
        )
        response.raise_for_status()
        return response.json()


async def register_pipeline_run(
    client: httpx.AsyncClient,
    pipeline_run_id: str,
    jurisdiction_ocdid: str,
    name: str | None,
    url: str | None,
) -> None:
    env = get_env_vars()
    response = await client.post(
        f"{env['CIVICPATCH_ORG_URL']}/api/v1/pipeline_runs/register",
        json={
            "pipeline_run_id": pipeline_run_id,
            "jurisdiction_ocdid": jurisdiction_ocdid,
            "name": name,
            "url": url,
        },
    )
    response.raise_for_status()


async def get_jurisdiction_info(
    client: httpx.AsyncClient, jurisdiction_ocdid: str
) -> dict:
    env = get_env_vars()
    response = await client.post(
        f"{env['CIVICPATCH_ORG_URL']}/api/v1/jurisdictions/by-ocdids",
        json={"ocdids": [jurisdiction_ocdid]},
    )
    response.raise_for_status()
    results = response.json().get("data", [])
    if not results:
        raise RuntimeError(f"Jurisdiction not found: {jurisdiction_ocdid}")
    return results[0]


async def update_pipeline_run_status(
    client: httpx.AsyncClient,
    logger,
    pipeline_run_id: str,
    jurisdiction_ocdid: str,
    status: str,
    progress: int,
    error_type: Optional[str] = None,
    error_detail: Optional[dict] = None,
):
    async def _update():
        env = get_env_vars()
        data = {
            "status": status,
            "progress": progress,
            "jurisdiction_ocdid": jurisdiction_ocdid,
            "error_type": error_type,
            "error_detail": error_detail,
        }

        response = await client.patch(
            f"{env['CIVICPATCH_ORG_URL']}/api/v1/pipeline_runs/{pipeline_run_id}/status",
            json=data,
        )
        logger.debug(f"Response: {response.status_code}, {response.text}")
        response.raise_for_status()
        return response

    return await with_retry(logger, _update)


async def submit_job_artifacts(
    client: httpx.AsyncClient,
    pipeline_run_id: str,
    jurisdiction_ocdid: str,
    zip_file_path: str,
    pipeline_run_status: str,
):
    env = get_env_vars()
    data = {
        "pipeline_run_id": pipeline_run_id,
        "jurisdiction_ocdid": jurisdiction_ocdid,
        "pipeline_run_status": pipeline_run_status,
        "env": env.get("APP_ENVIRONMENT") or "development",
    }
    file_name = os.path.basename(zip_file_path)

    with open(zip_file_path, "rb") as file_handle:
        files = {
            "file": (
                file_name,
                file_handle,
                "application/zip",
            )
        }
        response = await client.post(
            f"{env['CIVICPATCH_ORG_URL']}/api/v1/pipeline_runs/{pipeline_run_id}/submit",
            data=data,
            files=files,
        )
    return response


async def get_active_people(
    client: httpx.AsyncClient, logger, jurisdiction_ocdid: str
) -> List[dict]:
    return await search_people(client, logger, jurisdiction_ocdid, status="active")


async def get_role_config(logger) -> RoleConfig:
    """Fetch the role taxonomy from the backend API. It is one flat global list
    — migration 109 dropped per-jurisdiction scoping, so there is nothing to
    key the request on."""
    env = get_env_vars()

    async def _fetch():
        async with httpx.AsyncClient(
            headers={"Authorization": env["SERVICE_API_KEY"]},
            timeout=10,
        ) as client:
            response = await client.get(f"{env['CIVICPATCH_ORG_URL']}/api/v1/roles")
            response.raise_for_status()
            return response.json()

    response = await with_retry(logger, max_retries=3, func=_fetch)

    return RoleConfig.model_validate(response["data"])


async def search_people(
    client: httpx.AsyncClient,
    logger,
    jurisdiction_ocdid: str,
    status: Optional[str] = None,
) -> List[dict]:
    env = get_env_vars()
    params: dict = {"jurisdiction_ocdid": jurisdiction_ocdid}
    if status is not None:
        params["status"] = status
    url = f"{env['CIVICPATCH_ORG_URL']}/api/v1/people/search"
    response = await with_retry(logger, func=lambda: client.get(url, params=params))
    response.raise_for_status()
    return response.json().get("data", [])


async def get_organizations(
    client: httpx.AsyncClient, logger, jurisdiction_ocdid: str
) -> List[KnownOrganization]:
    """The bodies cp.org already holds for this jurisdiction, each with its posts.

    What the scrape steers by: which offices to look for, which divisions they sit in, and which
    body each belongs to. Read rather than researched, because cp.org is where that is already
    known — asking a model to guess it was only ever a stand-in for having somewhere to ask.
    """
    env = get_env_vars()
    url = f"{env['CIVICPATCH_ORG_URL']}/api/v1/organizations/{jurisdiction_ocdid}"
    response = await with_retry(logger, func=lambda: client.get(url))
    response.raise_for_status()
    organizations = response.json().get("data", {}).get("organizations", [])
    return [KnownOrganization.model_validate(organization) for organization in organizations]


async def get_roster_source_urls(client: httpx.AsyncClient, logger, jurisdiction_ocdid: str) -> List[str]:
    """The published roster's pages, as cp.org picks them for a re-scrape to start at."""
    env = get_env_vars()
    url = f"{env['CIVICPATCH_ORG_URL']}/api/v1/jurisdictions/{jurisdiction_ocdid}/roster-source-urls"
    response = await with_retry(logger, func=lambda: client.get(url))
    response.raise_for_status()
    return [url for group in response.json()["data"] for url in group["urls"]]


async def fetch_pipeline_run_status(
    client: httpx.AsyncClient, logger, pipeline_run_id: str
) -> Optional[str]:
    env = get_env_vars()
    url = f"{env['CIVICPATCH_ORG_URL']}/api/v1/pipeline_runs/{pipeline_run_id}/status"
    resp = await with_retry(logger, func=lambda: client.get(url))
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json().get("status")


async def fetch_pipeline_run_config(
    client: httpx.AsyncClient, logger, pipeline_run_id: str
) -> dict:
    async def _fetch():
        env = get_env_vars()
        resp = await client.get(
            f"{env['CIVICPATCH_ORG_URL']}/api/v1/pipeline_runs/{pipeline_run_id}/config"
        )
        resp.raise_for_status()
        return resp.json()

    return await with_retry(logger, _fetch)


async def patch_jurisdiction_extras(client: httpx.AsyncClient, jurisdiction_ocdid: str, extras: JurisdictionExtras) -> None:
    """Save cp.org's own fields on the jurisdiction: only the ones set on `extras` change."""
    env = get_env_vars()
    response = await client.patch(
        f"{env['CIVICPATCH_ORG_URL']}/api/v1/jurisdictions/{jurisdiction_ocdid}",
        # Only the fields set, each sent whole: `exclude_unset` would also drop a nested default.
        json=extras.model_dump(mode="json", include=extras.model_fields_set),
    )
    response.raise_for_status()


async def store_governing_law_source_page(
    client: httpx.AsyncClient, jurisdiction_ocdid: str, source_url: str, text: str
) -> dict:
    """Cache a collected page, stripped to markdown, through cp.org (the pipeline holds no
    bucket credentials). Answers the `governing_law_source_pages` row."""
    env = get_env_vars()
    response = await client.post(
        f"{env['CIVICPATCH_ORG_URL']}/api/v1/jurisdictions/{jurisdiction_ocdid}/governing_law_source_pages",
        json={"source_url": source_url, "text": text},
    )
    response.raise_for_status()
    return response.json()["data"]



async def reuse_governing_law_source_page(client: httpx.AsyncClient, jurisdiction_ocdid: str, source_url: str) -> dict | None:
    """A page another run stored from this url within a day, as this jurisdiction's row; None when
    there is none, and the url has to be fetched."""
    env = get_env_vars()
    response = await client.post(
        f"{env['CIVICPATCH_ORG_URL']}/api/v1/jurisdictions/{jurisdiction_ocdid}/governing_law_source_pages/reuse",
        json={"source_url": source_url},
    )
    response.raise_for_status()
    return response.json()["data"]

async def get_governing_law_source_page(client: httpx.AsyncClient, logger, jurisdiction_ocdid: str, source_page_id: str) -> dict:
    """The row with its text."""
    env = get_env_vars()
    url = f"{env['CIVICPATCH_ORG_URL']}/api/v1/jurisdictions/{jurisdiction_ocdid}/governing_law_source_pages/{source_page_id}"
    response = await with_retry(logger, func=lambda: client.get(url))
    response.raise_for_status()
    return response.json()["data"]


async def fetch_collector_config(client: httpx.AsyncClient, logger, pipeline_run_id: str) -> dict:
    """What the run is told at its start; cp.org answers by the run's kind."""
    async def _fetch():
        env = get_env_vars()
        resp = await client.get(
            f"{env['CIVICPATCH_ORG_URL']}/api/v1/pipeline_runs/{pipeline_run_id}/collector_config"
        )
        resp.raise_for_status()
        return resp.json()

    return await with_retry(logger, _fetch)


async def get_extras_organizations_by_input_hash(
    client: httpx.AsyncClient, logger, pipeline_run_id: str, input_hash: str
) -> GoverningLawOrganizations | None:
    """Another jurisdiction's answer read from the same inputs, or None when there is none yet."""
    async def _fetch() -> GoverningLawOrganizations | None:
        env = get_env_vars()
        resp = await client.get(
            f"{env['CIVICPATCH_ORG_URL']}/api/v1/pipeline_runs/{pipeline_run_id}/extras_organizations/{input_hash}"
        )
        if resp.status_code == httpx.codes.NOT_FOUND:
            return None
        resp.raise_for_status()
        return GoverningLawOrganizations.model_validate(resp.json()["data"])

    return await with_retry(logger, _fetch)


async def record_llm_calls(client: httpx.AsyncClient, logger, pipeline_run_id: str, calls: list[LLMCall]) -> None:
    """For a run that submits no artifacts. Safe to retry: cp.org skips a call it already holds."""
    async def _post():
        env = get_env_vars()
        resp = await client.post(
            f"{env['CIVICPATCH_ORG_URL']}/api/v1/pipeline_runs/{pipeline_run_id}/llm_calls",
            json={"llm_calls": [call.model_dump(mode="json") for call in calls]},
        )
        resp.raise_for_status()

    await with_retry(logger, _post)
