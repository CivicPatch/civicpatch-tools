import os
from typing import List, Optional

import httpx
from domain.models import Official
from fastapi import Request
from pipelines_environment import get_env_vars
from services.github_config_service import make_github_fetcher
from shared.schemas import RoleDefinition
from shared.utils.config_utils import (
    RoleConfig,
    load_role_config_for_jurisdiction,
)
from shared.utils.github_urls import derive_raw_base_url
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
    MAX_RETRIES = 3

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

    return await with_retry(logger, MAX_RETRIES, _update)


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


async def get_current_people(
    client: httpx.AsyncClient, jurisdiction_ocdid: str
) -> List[dict]:
    return await search_people(client, jurisdiction_ocdid, state="current")


async def get_role_config(jurisdiction_ocdid: str) -> Optional[dict]:
    """Fetch the merged role config response from the backend API."""
    env = get_env_vars()
    try:
        async with httpx.AsyncClient(
            headers={"Authorization": env["SERVICE_API_KEY"]},
            timeout=10,
        ) as client:
            response = await client.get(
                f"{env['CIVICPATCH_ORG_URL']}/api/v1/jurisdictions/config",
                params={"ocdid": jurisdiction_ocdid},
            )
            response.raise_for_status()
            return response.json()
    except Exception:
        return None


async def resolve_role_config(jurisdiction_ocdid: str) -> Optional[RoleConfig]:
    """Fetch merged role config from the backend API, GitHub fallback on failure."""
    raw = await get_role_config(jurisdiction_ocdid)
    if raw:
        roles_data = raw.get("data", {}).get("roles", [])
        return RoleConfig(
            roles=[
                RoleDefinition(
                    role=r["role"],
                    is_unique=r.get("is_unique", False),
                    aliases=r.get("aliases", []),
                )
                for r in roles_data
            ]
        )

    # Fallback to GitHub if backend unreachable
    env = get_env_vars()
    fetch_remote = make_github_fetcher(derive_raw_base_url(env["OPEN_DATA_REPO_URL"]))
    try:
        return load_role_config_for_jurisdiction(jurisdiction_ocdid, fetch_remote)
    except Exception:
        return None


async def search_people(
    client: httpx.AsyncClient,
    jurisdiction_ocdid: str,
    state: Optional[str] = None,
    name: Optional[str] = None,
) -> List[dict]:
    env = get_env_vars()
    params: dict = {"jurisdiction_ocdid": jurisdiction_ocdid}
    if state is not None:
        params["state"] = state
    if name is not None:
        params["name"] = name
    response = await client.get(
        f"{env['CIVICPATCH_ORG_URL']}/api/v1/people/search",
        params=params,
    )
    response.raise_for_status()
    return response.json().get("data", [])


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
    MAX_RETRIES = 5

    async def _fetch():
        env = get_env_vars()
        resp = await client.get(
            f"{env['CIVICPATCH_ORG_URL']}/api/v1/pipeline_runs/{request_id}/config"
        )
        resp.raise_for_status()
        return resp.json()

    return await with_retry(logger, MAX_RETRIES, _fetch)


async def batch_resolve_people(
    client: httpx.AsyncClient, jurisdiction_ocdid: str, people: List[Official]
) -> List[dict]:
    env = get_env_vars()
    people_dicts = [official.model_dump() for official in people]
    formatted_people_dicts = [
        {
            "id": person.get("id"),
            "name": person.get("name"),
            "email": person.get("email"),
        }
        for person in people_dicts
    ]

    data = {"jurisdiction_ocdid": jurisdiction_ocdid, "people": formatted_people_dicts}
    response = await client.post(
        f"{env['CIVICPATCH_ORG_URL']}/api/v1/people/batch-resolve",
        json=data,
    )
    response.raise_for_status()
    data = response.json()
    return data.get("data", [])
