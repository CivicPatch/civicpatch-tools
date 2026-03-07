import os
from typing import List, Optional, Dict, Any
import yaml
import base64
import httpx
import jwt
import time
from datetime import datetime, timezone
import logging

from schemas.common import PullRequest
from services import cache_service

timeout = httpx.Timeout(60.0)  

GITHUB_APP_ID = os.getenv("GITHUB_APP_ID")
GITHUB_APP_PRIVATE_KEY_BASE64 = os.getenv("GITHUB_APP_PRIVATE_KEY_BASE64")
GITHUB_APP_PRIVATE_KEY = base64.b64decode(GITHUB_APP_PRIVATE_KEY_BASE64).decode()
GITHUB_APP_INSTALLATION_ID = os.getenv("GITHUB_APP_INSTALLATION_ID")
OPEN_DATA_REPO_URL = os.getenv("OPEN_DATA_REPO_URL", "https://api.github.com/repos/CivicPatch/test-open-data")

CACHE_KEY = f"github:installation:{GITHUB_APP_INSTALLATION_ID}"

logger = logging.getLogger(__name__)

def _generate_jwt() -> str:
    logger.debug("Generating JWT for GitHub App authentication.")
    now = int(time.time())
    return jwt.encode(
        {"iat": now - 60, "exp": now + 600, "iss": GITHUB_APP_ID},
        GITHUB_APP_PRIVATE_KEY,
        algorithm="RS256",
    )

async def _fetch_github_token() -> tuple[str, float]:
    logger.debug("Fetching new GitHub installation access token.")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.github.com/app/installations/{GITHUB_APP_INSTALLATION_ID}/access_tokens",
            headers={
                "Authorization": f"Bearer {_generate_jwt()}",
                "Accept": "application/vnd.github+json",
            },
        )
        response.raise_for_status()
        data = response.json()

    token = data["token"]
    expires_at = datetime.strptime(data["expires_at"], "%Y-%m-%dT%H:%M:%SZ")
    expires_at = expires_at.replace(tzinfo=timezone.utc).timestamp()
    logger.info(f"Fetched new GitHub token, expires at {expires_at}")
    return token, expires_at

async def get_github_token():
    logger.debug(f"Retrieving GitHub token from cache with key: {CACHE_KEY}")
    token = cache_service.get_cached(CACHE_KEY)
    if token:
        logger.debug("GitHub token found in cache.")
        return token
    logger.info("GitHub token not found in cache, fetching new token.")
    token, expires_at = await _fetch_github_token()
    cache_service.set_cached(CACHE_KEY, token, expires_at)
    return token

async def get_default_headers() -> Dict[str, str]:
    logger.debug("Building default headers for GitHub API requests.")
    github_token = await get_github_token()
    return {
        "Authorization": f"Bearer {github_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

async def trigger_people_job_workflow(
    request_id: str,
    jurisdiction_ocdid: str,
    name: str | None = None,
    url: str | None = None,
):
    logger.info(f"Triggering people job workflow for request_id={request_id}, jurisdiction_ocdid={jurisdiction_ocdid}, name={name}, url={url}")
    data = {
        "ref": "main",
        "inputs": {
            "request_id": request_id,
            "jurisdiction_ocdid": jurisdiction_ocdid,
        }
    }

    if name:
        data["inputs"]["name"] = name
    if url:
        data["inputs"]["url"] = url
    default_headers = await get_default_headers()

    headers = {
        **default_headers,
        "Accept": "application/vnd.github+json",
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            "https://api.github.com/repos/CivicPatch/server/actions/workflows/data_scrape.yml/dispatches",
            headers=headers,
            json=data,
        )

    if response.status_code != 204:
        logger.error(f"Failed to trigger workflow: {response.status_code} - {response.text}")
        raise Exception(
            f"Failed to trigger workflow: {response.status_code} - {response.text}"
        )

    logger.info("Successfully triggered people job workflow.")
    return True

async def trigger_github_data_intake_workflow(
    user_email: str,
    server_url: str,
    request_id: str,
    jurisdiction_ocdid: str,
    zip_file_url: str
):
    logger.info(f"Triggering data intake workflow for request_id={request_id}, jurisdiction_ocdid={jurisdiction_ocdid}, user_email={user_email}, server_url={server_url}")
    data = {
        "ref": "main",
        "inputs": {
            "server_url": server_url,
            "user_email": user_email,
            "request_id": request_id,
            "jurisdiction_ocdid": jurisdiction_ocdid,
            "zip_file_url": zip_file_url
        },
    }

    default_headers = await get_default_headers()

    headers = {
        **default_headers,
        "Accept": "application/vnd.github+json",
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{OPEN_DATA_REPO_URL}/actions/workflows/data_intake.yml/dispatches",
            headers=headers,
            json=data,
        )

    if response.status_code != 204:
        logger.error(f"Failed to trigger data intake workflow: {response.status_code} - {response.text}")
        raise Exception(
            f"Failed to trigger workflow: {response.status_code} - {response.text}"
        )

    logger.info("Successfully triggered data intake workflow.")
    return True

async def get_github_file_contents(
        github_file_path: str,
        ref: Optional[str] = None,
    ) -> str | None:
    cache_key = f"github:file:{github_file_path}:{ref or 'main'}"
    logger.debug(f"Fetching GitHub file contents for {github_file_path} (ref={ref}) with cache_key={cache_key}")
    cached = cache_service.get_cached(cache_key)
    cached_etag = cached.get("etag") if cached else None
    cached_content = cached.get("content") if cached else None

    default_headers = await get_default_headers()
    url = f"{OPEN_DATA_REPO_URL}/contents/{github_file_path}"
    if ref:
        url += f"?ref={ref}"
    headers = {
        **default_headers,
        "Accept": "application/vnd.github.raw",
    }
    if cached_etag:
        headers["If-None-Match"] = cached_etag

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, headers=headers)

    if response.status_code == 304 and cached_content is not None:
        logger.debug(f"File {github_file_path} not modified since last fetch, using cached content.")
        return cached_content
    elif response.status_code == 200:
        file_content = response.text
        etag = response.headers.get("etag")
        logger.info(f"Fetched new version of {github_file_path} (etag: {etag}) from GitHub.")
        cache_service.set_cached(cache_key, {"content": file_content, "etag": etag})
        return file_content
    else:
        logger.error(f"Error fetching file contents: {github_file_path} {response.status_code} {response.text}")
        return None

async def get_open_pull_requests() -> List[PullRequest]:
    logger.debug("Fetching open pull requests from GitHub.")
    params = "state=open&per_page=100&sort=created&direction=desc"
    url = f"{OPEN_DATA_REPO_URL}/pulls?{params}"

    default_headers = await get_default_headers()
    headers = {
        **default_headers,
        "Accept": "application/vnd.github+json",
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, headers=headers)

    if response.status_code == 200:
        pull_requests = response.json()
        logger.info(f"Fetched {len(pull_requests)} open pull requests.")
        valid_pull_requests = [
            PullRequest(
                branch_name=pr["head"]["ref"],
                url=pr["html_url"],
            ) for pr in pull_requests
        ]
        return [pr for pr in valid_pull_requests if pr.jurisdiction_ocdid]
    else:
        logger.error(f"Error fetching pull requests: {response.status_code} {response.text}")
        return []
    
async def get_open_pull_request_by_branch_suffix(suffix: str) -> List[PullRequest]:
    logger.debug(f"Filtering open pull requests by branch suffix: {suffix}")
    pull_requests = await get_open_pull_requests()
    matching_prs = [pr for pr in pull_requests if pr.branch_name.endswith(suffix)]
    logger.info(f"Found {len(matching_prs)} pull requests matching suffix '{suffix}'.")
    return matching_prs

async def update_pull_request_file(
    branch_name: str,
    file_path: str,
    new_data: List[Dict[str, Any]],
    commit_message: str = "Automated update via API"
) -> bool:
    logger.info(f"Updating file '{file_path}' on branch '{branch_name}' via pull request.")
    default_headers = await get_default_headers()
    headers = {
        **default_headers,
    }
    contents_url = f"{OPEN_DATA_REPO_URL}/contents/{file_path}?ref={branch_name}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        contents_response = await client.get(contents_url, headers=headers)
        if contents_response.status_code != 200:
            logger.error(f"Failed to fetch file for update: {contents_response.status_code} {contents_response.text}")
            return False
        sha = contents_response.json()["sha"]
        serialized_data = yaml.dump(new_data, sort_keys=False, allow_unicode=True)
        encoded_content = base64.b64encode(serialized_data.encode("utf-8")).decode("utf-8")

        data = {
            "message": commit_message,
            "content": encoded_content,
            "sha": sha,
            "branch": branch_name
        }

        headers = {
            **default_headers,
            "Accept": "application/vnd.github+json",
        }

        update_response = await client.put(contents_url, json=data, headers=headers)
        if update_response.status_code in [200, 201]:
            logger.info(f"Successfully updated file '{file_path}' on branch '{branch_name}'.")
            return True
        else:
            logger.error(f"Error updating file: {update_response.status_code} {update_response.text}")
            return False

async def get_teams(user_oauth_token: str):
    logger.debug("Fetching user teams from GitHub.")
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {user_oauth_token}"
    }
    teams_url = "https://api.github.com/user/teams"
    async with httpx.AsyncClient() as client:
        response = await client.get(teams_url, headers=headers)
    if response.status_code == 200:
        teams = response.json()
        our_teams = [team for team in teams if team["organization"]["login"] == "CivicPatch"]
        team_names = [team["name"] for team in our_teams]
        logger.info(f"User is a member of {len(team_names)} CivicPatch teams: {team_names}")
        return team_names
    else:
        logger.error(f"Error fetching teams: {response.status_code} {response.text}")
        return []