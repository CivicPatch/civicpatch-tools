import os
from typing import List, Optional

import httpx
from fastapi import Request

from domain.models import Official
from utils.request_utils import with_retry
from pipelines_environment import get_env_vars

SERVER_SOURCE = os.getenv("CIVICPATCH_SERVER_SOURCE")


def _get_cookies(request: Optional[Request]):
    return request.cookies if request else None


def can_scrape_locally() -> bool:
    env = get_env_vars()
    return bool(env.get("GOOGLE_GEMINI_TOKEN") and env.get("TOGETHER_AI_TOKEN"))


# User calls
async def get_me(request: Request) -> dict:
    env = get_env_vars()
    last_exc = None
    for _ in range(3):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{env['CIVICPATCH_ORG_URL']}/api/v1/me", cookies=_get_cookies(request)
                )
                response.raise_for_status()
                return response.json()
        except httpx.ReadTimeout as e:
            last_exc = e
    raise last_exc


async def get_jurisdiction(jurisdiction_ocdid: str, request: Request) -> dict:
    env = get_env_vars()
    params = {"jurisdiction_ocdid": jurisdiction_ocdid, "with_geom": "true"}
    async with httpx.AsyncClient() as client:
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
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{env['CIVICPATCH_ORG_URL']}/api/v1/jurisdictions/history",
            params=params,
            cookies=_get_cookies(request),
        )
        response.raise_for_status()
        return response.json()


async def get_jurisdiction_info(jurisdiction_ocdid: str) -> dict:
    env = get_env_vars()
    system_auth_header = {"Authorization": env["SERVICE_API_KEY"]}
    async with httpx.AsyncClient(headers=system_auth_header) as client:
        response = await client.post(
            f"{env['CIVICPATCH_ORG_URL']}/api/v1/jurisdictions/by-ocdids",
            json={"ocdids": [jurisdiction_ocdid]},
        )
        response.raise_for_status()
        results = response.json().get("data", [])
        if not results:
            raise RuntimeError(f"Jurisdiction not found: {jurisdiction_ocdid}")
        return results[0]



async def update_job_status(
    logger, request_id: str, jurisdiction_ocdid: str, status: str, progress: int
):
    MAX_RETRIES = 3

    async def _update():
        env = get_env_vars()
        system_auth_header = {"Authorization": env["SERVICE_API_KEY"]}
        data = {
            "status": status,
            "progress": progress,
            "jurisdiction_ocdid": jurisdiction_ocdid,
        }
        print("data ", data)

        async with httpx.AsyncClient(headers=system_auth_header, timeout=15) as client:
            response = await client.patch(
                f"{env['CIVICPATCH_ORG_URL']}/api/v1/jobs/{request_id}/status",
                json=data,
            )
            logger.debug(f"Response: {response.status_code}, {response.text}")
            response.raise_for_status()
            return response

    return await with_retry(logger, MAX_RETRIES, _update)


async def submit_job_artifacts(
    request_id: str, jurisdiction_ocdid: str, zip_file_path: str, job_status: str
):
    env = get_env_vars()
    system_auth_header = {"Authorization": env["SERVICE_API_KEY"]}
    data = {
        "request_id": request_id,
        "jurisdiction_ocdid": jurisdiction_ocdid,
        "job_status": job_status,
    }
    file_name = os.path.basename(zip_file_path)

    # Use a context manager to ensure the file is closed after the request
    with open(zip_file_path, "rb") as file_handle:
        files = {
            "file": (
                file_name,
                file_handle,
                "application/zip",
            )
        }
        async with httpx.AsyncClient(headers=system_auth_header) as client:
            response = await client.post(
                f"{env['CIVICPATCH_ORG_URL']}/api/v1/jobs/{request_id}/submit",
                data=data,
                files=files,
            )
        return response


async def get_current_people(jurisdiction_ocdid: str) -> List[dict]:
    return await search_people(jurisdiction_ocdid, state="current")


async def search_people(
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
    system_auth_header = {"Authorization": env["SERVICE_API_KEY"]}
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{env['CIVICPATCH_ORG_URL']}/api/v1/people/search",
            params=params,
            headers=system_auth_header,
        )
        response.raise_for_status()
        return response.json().get("data", [])


async def upload_paused_context(request_id: str, context_json: str) -> None:
    env = get_env_vars()
    system_auth_header = {"Authorization": env["SERVICE_API_KEY"]}
    async with httpx.AsyncClient(headers=system_auth_header, timeout=15) as client:
        resp = await client.get(f"{env['CIVICPATCH_ORG_URL']}/api/v1/jobs/{request_id}/context/upload-url")
        resp.raise_for_status()
        upload_url = resp.json()["url"]
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.put(
            upload_url,
            content=context_json.encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()


async def download_paused_context(request_id: str) -> str:
    env = get_env_vars()
    system_auth_header = {"Authorization": env["SERVICE_API_KEY"]}
    async with httpx.AsyncClient(headers=system_auth_header, timeout=15) as client:
        resp = await client.get(f"{env['CIVICPATCH_ORG_URL']}/api/v1/jobs/{request_id}/context/download-url")
        resp.raise_for_status()
        download_url = resp.json()["url"]
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(download_url)
        resp.raise_for_status()
        return resp.text


async def delete_paused_context(request_id: str) -> None:
    env = get_env_vars()
    system_auth_header = {"Authorization": env["SERVICE_API_KEY"]}
    async with httpx.AsyncClient(headers=system_auth_header, timeout=15) as client:
        resp = await client.delete(f"{env['CIVICPATCH_ORG_URL']}/api/v1/jobs/{request_id}/context")
        resp.raise_for_status()


async def batch_resolve_people(
    jurisdiction_ocdid: str, people: List[Official]
) -> List[dict]:
    env = get_env_vars()
    system_auth_header = {"Authorization": env["SERVICE_API_KEY"]}
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
    async with httpx.AsyncClient(headers=system_auth_header) as client:
        response = await client.post(
            f"{env['CIVICPATCH_ORG_URL']}/api/v1/people/batch-resolve",
            json=data,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])
