import os
import requests
import json
from typing import List
from domain.models import Official


API_CIVICPATCH_ORG_TOKEN = os.getenv("API_CIVICPATCH_ORG_TOKEN")
API_CIVICPATCH_ORG_URL = os.getenv("API_CIVICPATCH_ORG_URL", "https://api.civicpatch.org")
# It's OK if this gets spoofed by third party runners -- this only lets us know if we
# need to limit /jobs API calls
SERVER_SOURCE = os.getenv("CIVICPATCH_SERVER_SOURCE") 
AUTH_HEADER = {
    "Authorization": API_CIVICPATCH_ORG_TOKEN
}

async def register_people_job(logger, request_id: str, arguments: dict):
    data = {
        "request_id": request_id,
        "arguments": arguments,
        "server_source": SERVER_SOURCE
    }
    response = requests.post(f"{API_CIVICPATCH_ORG_URL}/api/v1/jobs/people/register", 
                             headers=AUTH_HEADER, 
                             json=data
                             )
    if response.status_code != 200:
        logger.error(f"Failed to register job with api.civicpatch.org: {response.status_code} {response.text}")
    return response

async def update_people_job_status(logger, request_id: str, status: str, progress: int):
    data = {
        "status": status,
        "progress": progress
    }

    response = requests.patch(f"{API_CIVICPATCH_ORG_URL}/api/v1/jobs/people/{request_id}/status", 
                              headers=AUTH_HEADER, 
                              json=data)
    if response.status_code != 200:
        logger.error(f"Failed to update job status with api.civicpatch.org: {response.status_code} {response.text}")
    return response

async def update_people_job_result(logger, request_id: str, people: List[Official]):
    people_dicts = [official.model_dump() for official in people]
    data = {
        "data": people_dicts
    }

    response = requests.post(f"{API_CIVICPATCH_ORG_URL}/api/v1/jobs/people/{request_id}/result", 
                              headers=AUTH_HEADER, 
                              json=data)
    if response.status_code != 200:
        logger.error(f"Failed to update job result with api.civicpatch.org: {response.status_code} {response.text}")
    return response