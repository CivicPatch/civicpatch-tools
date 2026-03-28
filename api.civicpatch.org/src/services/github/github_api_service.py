import asyncio
import base64
import http
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from this import d
from typing import Any, Dict, List, Optional
from webbrowser import get

import httpx
import jwt
import shared.utils.id_utils
import yaml

import environment

from schemas.common import PullRequest
from services import cache_service

timeout = httpx.Timeout(60.0)

_RATE_LIMIT_THRESHOLD = 50  # sleep proactively when remaining drops below this


class RateLimitError(Exception):
    pass

## TODO: Replace bulk sync calls with graphql

def _get_github_config():
    env = environment.get_env_vars()
    app_id = env["GITHUB_APP_ID"]
    private_key = base64.b64decode(env["GITHUB_APP_PRIVATE_KEY_BASE64"]).decode()
    installation_id = env["GITHUB_APP_INSTALLATION_ID"]
    open_data_repo_url = env["OPEN_DATA_REPO_URL"]
    return app_id, private_key, installation_id, open_data_repo_url

logger = logging.getLogger(__name__)


def _generate_jwt() -> str:
    logger.debug("Generating JWT for GitHub App authentication.")
    app_id, private_key, _, _ = _get_github_config()
    now = int(time.time())
    return jwt.encode(
        {"iat": now - 60, "exp": now + 600, "iss": app_id},
        private_key,
        algorithm="RS256",
    )


async def _fetch_github_token() -> tuple[str, float]:
    logger.debug("Fetching new GitHub installation access token.")
    _, _, installation_id, _ = _get_github_config()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.github.com/app/installations/{installation_id}/access_tokens",
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
    _, _, installation_id, _ = _get_github_config()
    cache_key = f"github:installation:{installation_id}"
    logger.debug(f"Retrieving GitHub token from cache with key: {cache_key}")
    cached_token = await cache_service.get_cached(cache_key)
    if cached_token and "token" in cached_token:
        token = cached_token["token"]
        logger.debug("GitHub token found in cache.")
        return token
    logger.info("GitHub token not found in cache, fetching new token.")
    token, expires_at = await _fetch_github_token()
    await cache_service.set_cached(cache_key, {"token": token}, expires_at)
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
    logger.info(
        f"Triggering people job workflow for request_id={request_id}, jurisdiction_ocdid={jurisdiction_ocdid}, name={name}, url={url}"
    )
    data = {
        "ref": "main",
        "inputs": {
            "request_id": request_id,
            "jurisdiction_ocdid": jurisdiction_ocdid,
        },
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
        logger.error(
            f"Failed to trigger workflow: {response.status_code} - {response.text}"
        )
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
    zip_file_url: str,
):
    logger.info(
        f"Triggering data intake workflow for request_id={request_id}, jurisdiction_ocdid={jurisdiction_ocdid}, user_email={user_email}, server_url={server_url}"
    )
    data = {
        "ref": "main",
        "inputs": {
            "server_url": server_url,
            "user_email": user_email,
            "request_id": request_id,
            "jurisdiction_ocdid": jurisdiction_ocdid,
            "zip_file_url": zip_file_url,
        },
    }

    default_headers = await get_default_headers()

    headers = {
        **default_headers,
        "Accept": "application/vnd.github+json",
    }

    _, _, _, open_data_repo_url = _get_github_config()
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{open_data_repo_url}/actions/workflows/data_intake.yml/dispatches",
            headers=headers,
            json=data,
        )

    if response.status_code != 204:
        logger.error(
            f"Failed to trigger data intake workflow: {response.status_code} - {response.text}"
        )
        raise Exception(
            f"Failed to trigger workflow: {response.status_code} - {response.text}"
        )

    logger.info("Successfully triggered data intake workflow.")
    return True


async def cached_github_get(
    url: str,
    cache_key: str,
    accept: str = "application/vnd.github+json",
    return_json: bool = True,
) -> Any:
    """
    Wrapper for GET requests to GitHub API with ETag-based caching.
    If return_json is True, returns parsed JSON, else returns response.text.
    """
    cached = await cache_service.get_cached(cache_key)
    cached_etag = cached.get("etag") if cached else None
    cached_content = cached.get("content") if cached else None

    default_headers = await get_default_headers()
    headers = {
        **default_headers,
        "Accept": accept,
    }
    if cached_etag:
        headers["If-None-Match"] = cached_etag

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, headers=headers)

    if response.status_code == 304 and cached_content is not None:
        logger.debug(f"Cache hit for {url} (etag: {cached_etag})")
        return cached_content
    elif response.status_code == 200:
        etag = response.headers.get("etag")
        content = response.json() if return_json else response.text
        logger.debug(f"Fetched new data for {url} (etag: {etag})")
        await cache_service.set_cached(cache_key, {"content": content, "etag": etag})
        remaining = int(response.headers.get("X-RateLimit-Remaining", 9999))
        if remaining < _RATE_LIMIT_THRESHOLD:
            reset_at = int(response.headers.get("X-RateLimit-Reset", 0))
            wait = max(reset_at - time.time(), 1)
            logger.warning("GitHub rate limit low (%d remaining), sleeping %.0fs", remaining, wait)
            await asyncio.sleep(wait)
        return content
    elif response.status_code in (403, 429) and response.headers.get("X-RateLimit-Remaining") == "0":
        reset_at = response.headers.get("X-RateLimit-Reset", "unknown")
        raise RateLimitError(f"GitHub rate limit exceeded, resets at {reset_at}")
    else:
        logger.error(f"Error fetching {url}: {response.status_code} {response.text}")
        return None


async def get_github_file_contents(
    github_file_path: str,
    ref: Optional[str] = None,
) -> str | None:
    _, _, _, open_data_repo_url = _get_github_config()
    cache_key = f"github:file:{github_file_path}:{ref or 'main'}"
    url = f"{open_data_repo_url}/contents/{github_file_path}"
    if ref:
        url += f"?ref={ref}"
    return await cached_github_get(
        url, cache_key, accept="application/vnd.github.raw", return_json=False
    )


async def get_all_open_prs_raw(per_page: int = 100) -> List[Dict]:
    _, _, _, open_data_repo_url = _get_github_config()
    results = []
    page = 1
    while True:
        url = f"{open_data_repo_url}/pulls?state=open&per_page={per_page}&page={page}"
        cache_key = f"github:open_prs:page:{page}:per_page:{per_page}"
        prs = await cached_github_get(url, cache_key)
        if prs is None:
            raise RuntimeError(f"get_all_open_prs_raw: GitHub API error on page {page}")
        results.extend(prs)
        if len(prs) < per_page:
            break
        page += 1
    return results


async def get_open_pull_requests(
    jurisdiction_ocddid=None, state_code: str | None = None, per_page: int = 100
) -> List[PullRequest]:
    _, _, _, open_data_repo_url = _get_github_config()
    headers = await get_default_headers()
    all_prs = []
    page = 1
    while True:
        params = f"state=open&per_page={per_page}&page={page}&sort=created&direction=desc"
        url = f"{open_data_repo_url}/pulls?{params}"
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers)
        if response.status_code != 200:
            break
        batch = response.json()
        all_prs.extend(batch)
        if len(batch) < per_page:
            break
        page += 1
    valid_pull_requests = [
        PullRequest(branch_name=pr["head"]["ref"], url=pr["html_url"])
        for pr in all_prs
    ]
    if jurisdiction_ocddid:
        valid_pull_requests = [pr for pr in valid_pull_requests if pr.jurisdiction_ocdid == jurisdiction_ocddid]
    elif state_code:
        valid_pull_requests = [pr for pr in valid_pull_requests if f"state:{state_code}" in pr.jurisdiction_ocdid]
    return [pr for pr in valid_pull_requests if pr.jurisdiction_ocdid]


async def update_pull_request_file(
    branch_name: str,
    file_path: str,
    new_data: List[Dict[str, Any]],
    commit_message: str = "Automated update via API",
) -> bool:
    logger.info(
        f"Updating file '{file_path}' on branch '{branch_name}' via pull request."
    )
    _, _, _, open_data_repo_url = _get_github_config()
    default_headers = await get_default_headers()
    headers = {
        **default_headers,
    }
    contents_url = f"{open_data_repo_url}/contents/{file_path}?ref={branch_name}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        contents_response = await client.get(contents_url, headers=headers)
        if contents_response.status_code != 200:
            logger.error(
                f"Failed to fetch file for update: {contents_response.status_code} {contents_response.text}"
            )
            return False
        sha = contents_response.json()["sha"]
        serialized_data = yaml.dump(new_data, sort_keys=False, allow_unicode=True)
        encoded_content = base64.b64encode(serialized_data.encode("utf-8")).decode(
            "utf-8"
        )

        data = {
            "message": commit_message,
            "content": encoded_content,
            "sha": sha,
            "branch": branch_name,
        }

        headers = {
            **default_headers,
            "Accept": "application/vnd.github+json",
        }

        update_response = await client.put(contents_url, json=data, headers=headers)
        if update_response.status_code in [200, 201]:
            logger.info(
                f"Successfully updated file '{file_path}' on branch '{branch_name}'."
            )
            return True
        else:
            logger.error(
                f"Error updating file: {update_response.status_code} {update_response.text}"
            )
            return False


async def get_teams(user_oauth_token: str):
    logger.debug("Fetching user teams from GitHub.")
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {user_oauth_token}",
    }
    teams_url = "https://api.github.com/user/teams"
    async with httpx.AsyncClient() as client:
        response = await client.get(teams_url, headers=headers)
    if response.status_code == 200:
        teams = response.json()
        our_teams = [
            team for team in teams if team["organization"]["login"] == "CivicPatch"
        ]
        team_names = [team["name"] for team in our_teams]
        logger.info(
            f"User is a member of {len(team_names)} CivicPatch teams: {team_names}"
        )
        return team_names
    else:
        logger.error(f"Error fetching teams: {response.status_code} {response.text}")
        return []


async def get_pull_request_workflow_context(
    request_id: str, jurisdiction_ocdid: str
) -> dict | None:
    """Fetch and parse workflow_context.json from a specific PR branch."""
    folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    file_path = f"data_source/{folder}/workflow_context.json"
    branch_name = shared.utils.id_utils.make_git_branch(jurisdiction_ocdid, request_id)
    content = await get_github_file_contents(file_path, ref=branch_name)
    if content is None:
        return None
    try:
        return json.loads(content)
    except Exception as e:
        logger.error(
            f"Failed to parse workflow_context.json on branch {branch_name}: {e}"
        )
        return None


async def get_pull_request_file_yaml(
    request_id: str, jurisdiction_ocdid: str, file_path: str
) -> list | dict | None:
    """Fetch and parse a YAML file from a specific branch."""
    branch_name = shared.utils.id_utils.make_git_branch(jurisdiction_ocdid, request_id)
    content = await get_github_file_contents(file_path, ref=branch_name)
    if content is None:
        return None
    try:
        return yaml.safe_load(content)
    except Exception as e:
        logger.error(
            f"Failed to parse YAML from {file_path} on branch {branch_name}: {e}"
        )
        return None


async def get_pull_request_review_state(pr_number: int) -> str | None:
    """Returns the effective review state ('approved' or 'changes_requested') or None."""
    _, _, _, open_data_repo_url = _get_github_config()
    url = f"{open_data_repo_url}/pulls/{pr_number}/reviews"
    cache_key = f"github:pr_reviews:{pr_number}"
    reviews = await cached_github_get(url, cache_key)
    if not reviews:
        return None
    for review in reversed(reviews):
        state = review.get("state", "").lower()
        if state in ("approved", "changes_requested"):
            return state
    return None


async def get_pull_request(pull_request_number: str) -> dict | None:
    _, _, _, open_data_repo_url = _get_github_config()
    async with httpx.AsyncClient() as client:
        default_headers = await get_default_headers()
        response = await client.get(
            f"{open_data_repo_url}/pulls/{pull_request_number}",
            headers=default_headers,
        )
        if response.status_code != 200:
            return None
        return response.json()


async def close_pull_request(pull_request_number: str) -> bool:
    _, _, _, open_data_repo_url = _get_github_config()
    async with httpx.AsyncClient() as client:
        default_headers = await get_default_headers()
        response = await client.patch(
            f"{open_data_repo_url}/pulls/{pull_request_number}",
            headers=default_headers,
            json={"state": "closed"},
        )
        if response.status_code != 200:
            logger.error(f"Failed to close PR {pull_request_number}: {response.status_code} {response.text}")
        return response.status_code == 200


async def merge_pull_request(pull_request_number: str) -> str | None:
    """Returns None on success, or a GitHub error message string on failure."""
    data = {
        "commit_title": "Approved in app",
        "commit_message": "Approved in app",
        "merge_method": "squash",
    }

    _, _, _, open_data_repo_url = _get_github_config()
    async with httpx.AsyncClient() as client:
        default_headers = await get_default_headers()
        response = await client.put(
            f"{open_data_repo_url}/pulls/{pull_request_number}/merge",
            headers=default_headers,
            json=data,
        )

        if response.status_code != 200:
            github_message = response.json().get("message", "Unknown error")
            logger.error(f"GitHub merge failed ({response.status_code}): {github_message}")
            return github_message
        return None


async def update_pull_request_branch(pull_request_number: str) -> str | None:
    """Updates the PR branch to be current with the base branch.
    Returns None on success, or an error message string on failure."""
    _, _, _, open_data_repo_url = _get_github_config()
    async with httpx.AsyncClient() as client:
        default_headers = await get_default_headers()
        response = await client.put(
            f"{open_data_repo_url}/pulls/{pull_request_number}/update-branch",
            headers=default_headers,
            json={},
        )
        # 202 = accepted (async), 200 = done
        if response.status_code not in (200, 202):
            github_message = response.json().get("message", "Unknown error")
            logger.error(f"Branch update failed ({response.status_code}): {github_message}")
            return github_message
        return None
