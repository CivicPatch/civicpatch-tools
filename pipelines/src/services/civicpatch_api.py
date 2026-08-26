import os
from typing import List, Optional

import httpx
from fastapi import Request
from pipelines_environment import get_env_vars
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


# User calls
async def get_me(request: Request) -> dict:
    env = get_env_vars()
    last_exc: httpx.ReadTimeout | None = None
    for _ in range(3):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{env['CIVICPATCH_ORG_URL']}/api/v1/me",
                    cookies=_get_cookies(request),
                )
                response.raise_for_status()
                return response.json()
        except httpx.ReadTimeout as e:
            last_exc = e
    raise last_exc or httpx.ReadTimeout("All retries failed")


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


async def get_people_job_history(jurisdiction_ocdid: str, request: Request) -> dict:
    env = get_env_vars()
    params = {"jurisdiction_ocdid": jurisdiction_ocdid}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{env['CIVICPATCH_ORG_URL']}/api/v1/jurisdictions/history",
            params=params,
            cookies=_get_cookies(request),
        )
        response.raise_for_status()
        return response.json()


async def register_pipeline_run(
    client: httpx.AsyncClient,
    request_id: str,
    jurisdiction_ocdid: str,
    name: str | None,
    url: str | None,
) -> None:
    env = get_env_vars()
    response = await client.post(
        f"{env['CIVICPATCH_ORG_URL']}/api/v1/pipeline_runs/register",
        json={
            "request_id": request_id,
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
    request_id: str,
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
            f"{env['CIVICPATCH_ORG_URL']}/api/v1/pipeline_runs/{request_id}/status",
            json=data,
        )
        logger.debug(f"Response: {response.status_code}, {response.text}")
        response.raise_for_status()
        return response

    return await with_retry(logger, _update)


async def submit_job_artifacts(
    client: httpx.AsyncClient,
    request_id: str,
    jurisdiction_ocdid: str,
    zip_file_path: str,
    pipeline_run_status: str,
):
    env = get_env_vars()
    data = {
        "request_id": request_id,
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
            f"{env['CIVICPATCH_ORG_URL']}/api/v1/pipeline_runs/{request_id}/submit",
            data=data,
            files=files,
        )
    return response


async def get_active_people(
    client: httpx.AsyncClient, jurisdiction_ocdid: str
) -> List[dict]:
    return await search_people(client, jurisdiction_ocdid, status="active")


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
    jurisdiction_ocdid: str,
    status: Optional[str] = None,
) -> List[dict]:
    env = get_env_vars()
    params: dict = {"jurisdiction_ocdid": jurisdiction_ocdid}
    if status is not None:
        params["status"] = status
    response = await client.get(
        f"{env['CIVICPATCH_ORG_URL']}/api/v1/people/search",
        params=params,
    )
    response.raise_for_status()
    return response.json().get("data", [])


async def get_posts(
    client: httpx.AsyncClient, jurisdiction_ocdid: str
) -> List[dict]:
    """The posts cp.org already holds for this jurisdiction, flattened out of their bodies.

    What the scrape steers by: which offices to look for and which divisions they sit in. Read
    rather than researched, because cp.org is where that is already known — asking a model to
    guess it was only ever a stand-in for having somewhere to ask.
    """
    env = get_env_vars()
    response = await client.get(
        f"{env['CIVICPATCH_ORG_URL']}/api/v1/posts/{jurisdiction_ocdid}"
    )
    response.raise_for_status()
    organizations = response.json().get("data", {}).get("organizations", [])
    return [post for organization in organizations for post in organization["posts"]]


async def fetch_pipeline_run_status(
    client: httpx.AsyncClient, request_id: str
) -> Optional[str]:
    env = get_env_vars()
    resp = await client.get(
        f"{env['CIVICPATCH_ORG_URL']}/api/v1/pipeline_runs/{request_id}/status"
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json().get("status")


async def fetch_pipeline_run_config(
    client: httpx.AsyncClient, logger, request_id: str
) -> dict:
    async def _fetch():
        env = get_env_vars()
        resp = await client.get(
            f"{env['CIVICPATCH_ORG_URL']}/api/v1/pipeline_runs/{request_id}/config"
        )
        resp.raise_for_status()
        return resp.json()

    return await with_retry(logger, _fetch)
