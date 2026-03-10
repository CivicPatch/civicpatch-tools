import os
import httpx
from typing import List, Optional
from domain.models import Official
from fastapi import Request
from utils.request_utils import with_retry

SERVICE_API_KEY = os.getenv("SERVICE_API_KEY", "")
API_CIVICPATCH_ORG_URL = os.getenv("API_CIVICPATCH_ORG_URL", "https://api.civicpatch.org")
SERVER_SOURCE = os.getenv("CIVICPATCH_SERVER_SOURCE")
SYSTEM_AUTH_HEADER = {
    "Authorization": SERVICE_API_KEY
}

def _get_cookies(request: Optional[Request]):
    return request.cookies if request else None

can_scrape_locally = bool(os.getenv("GOOGLE_GEMINI_TOKEN") and os.getenv("TOGETHER_AI_TOKEN"))

# User calls
async def get_me(request: Request) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_CIVICPATCH_ORG_URL}/api/v1/me",
            cookies=_get_cookies(request)
        )
        response.raise_for_status()
        return response.json()

async def get_people_job_history(jurisdiction_ocdid: str, request: Request) -> dict:
    params = {
        "jurisdiction_ocdid": jurisdiction_ocdid
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_CIVICPATCH_ORG_URL}/api/v1/jurisdictions/history",
            params=params,
            cookies=_get_cookies(request)
        )
        response.raise_for_status()
        return response.json()

# System calls
async def register_people_job(logger, request_id: str, arguments: dict):
    data = {
        "request_id": request_id,
        "arguments": arguments,
        "server_source": SERVER_SOURCE
    }
    async with httpx.AsyncClient(headers=SYSTEM_AUTH_HEADER) as client:
        response = await client.post(
            f"{API_CIVICPATCH_ORG_URL}/api/v1/jobs/people/register",
            json=data,
        )
        if response.status_code != 200:
            logger.error(f"Failed to register job with api.civicpatch.org: {response.status_code} {response.text}")
        return response

async def update_job_status(logger, request_id: str, jurisdiction_ocdid: str, status: str, progress: int):
    MAX_RETRIES = 3
    async def _update():
        data = {
            "status": status,
            "progress": progress,
            "jurisdiction_ocdid": jurisdiction_ocdid
        }
        print("data ", data)

        async with httpx.AsyncClient(headers=SYSTEM_AUTH_HEADER, timeout=15) as client:
            response = await client.patch(
                f"{API_CIVICPATCH_ORG_URL}/api/v1/jobs/people/{request_id}/status",
                json=data,
            )
            logger.debug(f"Response: {response.status_code}, {response.text}")
            response.raise_for_status()
            return response
    return await with_retry(logger, MAX_RETRIES, _update)

async def update_people_job_result(logger, request_id: str, people: List[Official]):
    people_dicts = [official.model_dump() for official in people]
    data = {
        "data": people_dicts
    }
    async with httpx.AsyncClient(headers=SYSTEM_AUTH_HEADER) as client:
        response = await client.post(
            f"{API_CIVICPATCH_ORG_URL}/api/v1/jobs/people/{request_id}/result",
            json=data,
        )
        if response.status_code != 200:
            logger.error(f"Failed to update job result with api.civicpatch.org: {response.status_code} {response.text}")
        return response

async def batch_resolve_people(jurisdiction_ocdid: str, people: List[Official]) -> List[dict]:
    people_dicts = [official.model_dump() for official in people]
    formatted_people_dicts = [
        {
         "id": person.get("id"),
         "name": person.get("name"), 
         "email": person.get("email")
         } 
         for person in people_dicts]

    data = {
        "jurisdiction_ocdid": jurisdiction_ocdid,
        "people": formatted_people_dicts
    }
    async with httpx.AsyncClient(headers=SYSTEM_AUTH_HEADER) as client:
        response = await client.post(
            f"{API_CIVICPATCH_ORG_URL}/api/v1/people/batch-resolve",
            json=data,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])
    
async def submit_job_artifacts(request_id: str, jurisdiction_ocdid: str, zip_file_path: str):
    data = {
        "request_id": request_id,
        "jurisdiction_ocdid": jurisdiction_ocdid,
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
        async with httpx.AsyncClient(headers=SYSTEM_AUTH_HEADER) as client:
            response = await client.post(
                f"{API_CIVICPATCH_ORG_URL}/api/v1/jobs/people/{request_id}/submit",
                data=data,
                files=files
            )
        return response