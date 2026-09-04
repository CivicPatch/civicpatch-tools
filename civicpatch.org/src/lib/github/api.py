import asyncio
import base64
import json
import logging
import time
from typing import Any, Dict, List, Optional

import httpx
import shared.utils.id_utils
from pydantic import BaseModel
from shared.utils.yaml_utils import yaml_load

import lib.cache as cache_service
from lib.github.auth import _get_github_config, get_default_headers

timeout = httpx.Timeout(60.0)

_RATE_LIMIT_THRESHOLD = 50  # sleep proactively when remaining drops below this

# open-data's default branch. The bare "main" defaults elsewhere in this module predate it.
DEFAULT_BRANCH = "main"


class RateLimitError(Exception):
    pass


class GithubUnavailableError(Exception):
    pass


class RepoTree(BaseModel):
    entries: dict[str, str]  # path -> blob SHA, blobs (files only)
    truncated: bool


## TODO: Replace bulk sync calls with graphql

logger = logging.getLogger(__name__)


async def trigger_people_job_workflow(
    changeset_id: str,
    jurisdiction_ocdid: str,
    name: str | None = None,
    url: str | None = None,
    source_urls: list[str] | None = None,
):
    logger.info(
        f"Triggering people job workflow for changeset_id={changeset_id}, jurisdiction_ocdid={jurisdiction_ocdid}, name={name}, url={url}"
    )
    data = {
        "ref": "main",
        "inputs": {
            "changeset_id": changeset_id,
            "jurisdiction_ocdid": jurisdiction_ocdid,
        },
    }

    if name:
        data["inputs"]["name"] = name
    if url:
        data["inputs"]["url"] = url
    if source_urls:
        data["inputs"]["source_urls"] = json.dumps(source_urls)
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
            logger.warning(
                "GitHub rate limit low (%d remaining), sleeping %.0fs", remaining, wait
            )
            await asyncio.sleep(wait)
        return content
    elif (
        response.status_code in (403, 429)
        and response.headers.get("X-RateLimit-Remaining") == "0"
    ):
        reset_at = response.headers.get("X-RateLimit-Reset", "unknown")
        raise RateLimitError(f"GitHub rate limit exceeded, resets at {reset_at}")
    elif response.status_code == 404:
        logger.debug(f"File not found (404): {url}")
        return None
    else:
        logger.error(
            f"Unexpected response fetching {url}: {response.status_code} {response.text}"
        )
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


def _matches(existing: dict, encoded: str) -> bool:
    if existing.get("encoding") != "base64":
        return False
    return "".join(existing.get("content", "").split()) == encoded


async def upsert_github_file(
    branch_name: str,
    file_path: str,
    content_str: str,
    commit_message: str,
    author: dict | None = None,
    repo_url: str | None = None,
    headers: dict | None = None,
) -> str | None:
    """Returns the URL of the commit it created, or None if the write was rejected.

    A URL rather than a bool because callers need somewhere to point at what they wrote;
    both are truthy-checked the same way.
    """
    _, _, _, open_data_repo_url = _get_github_config()
    target_repo = repo_url or open_data_repo_url
    auth_headers = headers if headers is not None else await get_default_headers()
    contents_url = f"{target_repo}/contents/{file_path}?ref={branch_name}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        get_resp = await client.get(contents_url, headers=auth_headers)
        encoded = base64.b64encode(content_str.encode()).decode()
        payload: dict = {
            "message": commit_message,
            "content": encoded,
            "branch": branch_name,
        }
        if get_resp.status_code == 200:
            existing = get_resp.json()
            payload["sha"] = existing["sha"]
            if _matches(existing, encoded):
                return existing.get("html_url")
        if author:
            payload["author"] = author
        put_resp = await client.put(
            contents_url,
            json=payload,
            headers={**auth_headers, "Accept": "application/vnd.github+json"},
        )
        if put_resp.status_code in (200, 201):
            return put_resp.json().get("commit", {}).get("html_url")
        logger.error(
            f"upsert_github_file failed ({put_resp.status_code}): {put_resp.text}"
        )
        return None


async def get_pull_request_context(
    changeset_id: str, jurisdiction_ocdid: str
) -> dict | None:
    """Fetch and parse pipeline_run_context.json from a specific PR branch."""
    folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    file_path = f"data_source/{folder}/pipeline_run_context.json"
    branch_name = shared.utils.id_utils.make_job_branch(
        jurisdiction_ocdid, changeset_id
    )
    content = await get_github_file_contents(file_path, ref=branch_name)
    if content is None:
        return None
    try:
        return json.loads(content)
    except Exception as e:
        logger.error(
            f"Failed to parse pipeline_run_context.json on branch {branch_name}: {e}"
        )
        return None


async def get_pull_request_file_yaml(
    changeset_id: str, jurisdiction_ocdid: str, file_path: str
) -> list | dict | None:
    """Fetch and parse a YAML file from a specific branch."""
    branch_name = shared.utils.id_utils.make_job_branch(
        jurisdiction_ocdid, changeset_id
    )
    content = await get_github_file_contents(file_path, ref=branch_name)
    if content is None:
        return None
    try:
        return yaml_load(content)
    except Exception as e:
        logger.error(
            f"Failed to parse YAML from {file_path} on branch {branch_name}: {e}"
        )
        return None


async def get_pull_request(pull_request_number: str) -> dict | None:
    _, _, _, open_data_repo_url = _get_github_config()
    url = f"{open_data_repo_url}/pulls/{pull_request_number}"
    cache_key = f"github:pr:{pull_request_number}"
    return await cached_github_get(url, cache_key)


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
            logger.error(
                f"Failed to close PR {pull_request_number}: {response.status_code} {response.text}"
            )
        return response.status_code == 200


async def get_pull_request_mergeability(
    pull_request_number: str, wait_for_change_from: str | None = None
) -> str | None:
    """Polls until GitHub has computed mergeability (up to 10 attempts, 2s apart).
    Returns the mergeable_state string ("clean", "dirty", "blocked", etc.)
    or None if still unknown after all retries.

    If wait_for_change_from is provided, keeps polling until the state differs from
    that value — useful after a branch update to avoid reading a stale result."""
    _, _, _, open_data_repo_url = _get_github_config()
    async with httpx.AsyncClient() as client:
        default_headers = await get_default_headers()
        for _ in range(10):
            response = await client.get(
                f"{open_data_repo_url}/pulls/{pull_request_number}",
                headers=default_headers,
            )
            if response.status_code != 200:
                return None
            data = response.json()
            state = data.get("mergeable_state")
            if data.get("mergeable") is not None and state not in (
                "unknown",
                wait_for_change_from,
            ):
                return state
            await asyncio.sleep(2)
    return None


async def merge_pull_request(
    pull_request_number: str, approved_by: str | None = None
) -> str | None:
    """Returns None on success, or a GitHub error message string on failure."""
    label = f"Approved by {approved_by}" if approved_by else "Approved by unknown"
    data = {
        "commit_title": label,
        "commit_message": label,
        "merge_method": "squash",
    }

    _, _, _, open_data_repo_url = _get_github_config()
    async with httpx.AsyncClient() as client:
        default_headers = await get_default_headers()
        github_message = "Unknown error"
        for attempt in range(2):
            response = await client.put(
                f"{open_data_repo_url}/pulls/{pull_request_number}/merge",
                headers=default_headers,
                json=data,
            )
            if response.status_code == 200:
                return None
            github_message = response.json().get("message", "Unknown error")
            # GitHub can transiently report "not mergeable" immediately after a commit is pushed
            # while it recomputes mergeability; retry once to let it settle
            if (
                attempt == 0
                and response.status_code == 405
                and "not mergeable" in github_message.lower()
            ):
                logger.warning(
                    f"PR {pull_request_number} transiently not mergeable, retrying after recompute"
                )
                await asyncio.sleep(5)
                continue
            logger.error(
                f"GitHub merge failed ({response.status_code}): {github_message}"
            )
            return github_message
    return github_message


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
            logger.error(
                f"Branch update failed ({response.status_code}): {github_message}"
            )
            return github_message
        return None


async def create_branch(
    branch_name: str,
    base_ref: str = "main",
    repo_url: str | None = None,
    headers: dict | None = None,
) -> str | None:
    """Creates a new branch off base_ref in the target repo.
    Returns None on success, or an error message string on failure."""
    _, _, _, open_data_repo_url = _get_github_config()
    target_repo = repo_url or open_data_repo_url
    auth_headers = headers if headers is not None else await get_default_headers()
    async with httpx.AsyncClient(timeout=timeout) as client:
        ref_response = await client.get(
            f"{target_repo}/git/ref/heads/{base_ref}",
            headers=auth_headers,
        )
        if ref_response.status_code != 200:
            message = ref_response.json().get("message", "Unknown error")
            logger.error(
                f"Failed to resolve {base_ref} SHA ({ref_response.status_code}): {message}"
            )
            return message
        sha = ref_response.json()["object"]["sha"]

        create_response = await client.post(
            f"{target_repo}/git/refs",
            headers=auth_headers,
            json={"ref": f"refs/heads/{branch_name}", "sha": sha},
        )
        if create_response.status_code != 201:
            message = create_response.json().get("message", "Unknown error")
            logger.error(
                f"Failed to create branch {branch_name!r} ({create_response.status_code}): {message}"
            )
            return message
    logger.info(f"Created branch {branch_name!r} off {base_ref} at {sha}")
    return None


async def create_pull_request(
    branch_name: str,
    title: str,
    body: str = "",
    base: str = "main",
    repo_url: str | None = None,
    headers: dict | None = None,
    labels: list[str] | None = None,
) -> tuple[int, str] | tuple[None, str]:
    """Opens a PR in the target repo from branch_name into base.
    Returns (pr_number, pr_url) on success, or (None, error_message) on failure.
    head overrides the PR head ref"""
    _, _, _, open_data_repo_url = _get_github_config()
    target_repo = repo_url or open_data_repo_url
    auth_headers = headers if headers is not None else await get_default_headers()
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{target_repo}/pulls",
            headers=auth_headers,
            json={
                "title": title,
                "body": body,
                "head": branch_name,
                "base": base,
            },
        )
        if response.status_code != 201:
            resp_body = response.json()
            message = resp_body.get("message", "Unknown error")
            errors = resp_body.get("errors", [])
            logger.error(
                f"Failed to create PR from {branch_name!r} ({response.status_code}): {message} errors={errors}"
            )
            return None, message
        data = response.json()
    pr_number = data["number"]
    logger.info(f"Created PR #{pr_number} from {branch_name!r}: {data['html_url']}")
    if labels:
        await add_pr_labels(
            pr_number, labels, repo_url=target_repo, headers=auth_headers
        )
    return pr_number, data["html_url"]


async def add_pr_labels(
    pr_number: int, labels: list[str], repo_url: str, headers: dict
) -> None:
    """Upserts labels on the repo then applies them to the PR. Best-effort — logs and returns on failure."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        for label in labels:
            response = await client.post(
                f"{repo_url}/labels",
                headers=headers,
                json={"name": label, "color": "0075ca"},
            )
            if response.status_code not in (201, 422):
                logger.warning(
                    f"Unexpected status creating label {label!r}: {response.status_code}"
                )
        response = await client.post(
            f"{repo_url}/issues/{pr_number}/labels",
            headers=headers,
            json={"labels": labels},
        )
        if response.status_code != 200:
            logger.warning(
                f"Failed to apply labels {labels} to PR #{pr_number}: {response.status_code}"
            )


async def create_issue(
    title: str,
    body: str = "",
    labels: list[str] | None = None,
    repo_url: str | None = None,
    headers: dict | None = None,
) -> tuple[int, str] | tuple[None, str]:
    """Opens an issue in the target repo.
    Returns (issue_number, issue_url) on success, or (None, error_message) on failure."""
    _, _, _, open_data_repo_url = _get_github_config()
    target_repo = repo_url or open_data_repo_url
    auth_headers = headers if headers is not None else await get_default_headers()
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{target_repo}/issues",
            headers=auth_headers,
            json={"title": title, "body": body, "labels": labels or []},
        )
        if response.status_code != 201:
            resp_body = response.json()
            message = resp_body.get("message", "Unknown error")
            errors = resp_body.get("errors", [])
            logger.error(
                f"Failed to create issue {title!r} ({response.status_code}): {message} errors={errors}"
            )
            return None, message
        data = response.json()
    issue_number = data["number"]
    logger.info(f"Created issue #{issue_number}: {data['html_url']}")
    return issue_number, data["html_url"]


async def get_tree(repo_url: str) -> RepoTree:
    url = f"{repo_url}/git/trees/main?recursive=1"
    response = await cached_github_get(url, f"github:tree:{repo_url}:main")
    if response is None:
        raise GithubUnavailableError(f"Tree fetch returned no data: {url}")
    entries = {
        item["path"]: item["sha"] for item in response["tree"] if item["type"] == "blob"
    }
    return RepoTree(entries=entries, truncated=response["truncated"])
