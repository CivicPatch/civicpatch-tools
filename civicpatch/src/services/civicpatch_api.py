import os
import httpx
from typing import List, Optional
from domain.models import Official
from fastapi import Request

SERVICE_API_KEY = os.getenv("SERVICE_API_KEY")
API_CIVICPATCH_ORG_URL = os.getenv("API_CIVICPATCH_ORG_URL", "https://api.civicpatch.org")
SERVER_SOURCE = os.getenv("CIVICPATCH_SERVER_SOURCE")
AUTH_HEADER = {
    "Authorization": SERVICE_API_KEY
}

client = httpx.AsyncClient(headers=AUTH_HEADER)

def _get_cookies(request: Optional[Request]):
    return request.cookies if request else None


can_scrape_locally = bool(os.getenv("GOOGLE_GEMINI_TOKEN") and os.getenv("TOGETHER_AI_TOKEN"))

async def get_me(request: Optional[Request] = None):
    response = await client.get(
        f"{API_CIVICPATCH_ORG_URL}/api/v1/me",
        cookies=_get_cookies(request)
    )
    response.raise_for_status()
    return response.json()

async def register_people_job(logger, request_id: str, arguments: dict, request: Optional[Request] = None):
    data = {
        "request_id": request_id,
        "arguments": arguments,
        "server_source": SERVER_SOURCE
    }
    response = await client.post(
        f"{API_CIVICPATCH_ORG_URL}/api/v1/jobs/people/register",
        json=data,
        cookies=_get_cookies(request)
    )
    if response.status_code != 200:
        logger.error(f"Failed to register job with api.civicpatch.org: {response.status_code} {response.text}")
    return response

async def update_job_status(request_id: str, jurisdiction_ocdid: str, status: str, progress: int, request: Optional[Request] = None):
    data = {
        "status": status,
        "progress": progress,
        "jurisdiction_ocdid": jurisdiction_ocdid
    }
    response = await client.patch(
        f"{API_CIVICPATCH_ORG_URL}/api/v1/jobs/people/{request_id}/status",
        json=data,
        cookies=_get_cookies(request)
    )
    return response

async def update_people_job_result(logger, request_id: str, people: List[Official], request: Optional[Request] = None):
    people_dicts = [official.model_dump() for official in people]
    data = {
        "data": people_dicts
    }
    response = await client.post(
        f"{API_CIVICPATCH_ORG_URL}/api/v1/jobs/people/{request_id}/result",
        json=data,
        cookies=_get_cookies(request)
    )
    if response.status_code != 200:
        logger.error(f"Failed to update job result with api.civicpatch.org: {response.status_code} {response.text}")
    return response

async def get_people_job_history(jurisdiction_ocdid: str, request: Optional[Request] = None):
    params = {
        "jurisdiction_ocdid": jurisdiction_ocdid
    }
    response = await client.get(
        f"{API_CIVICPATCH_ORG_URL}/api/v1/jurisdictions/history",
        params=params,
        cookies=_get_cookies(request)
    )
    response.raise_for_status()
    return response.json()