import hashlib
import hmac
import json
import logging
from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

import shared.utils.id_utils as id_utils
from shared.utils.statuses import PullRequestStatus
import database.issues as issues_db
from services.pull_request_sync import apply_pull_request_status
from environment import get_env_vars

logger = logging.getLogger(__name__)


def _verify_signature(body: bytes, secret: str, signature: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _parse_pr_status(payload: dict[str, Any]) -> tuple[str, str, str | None, str | None] | None:
    """Returns (request_id, status, merged_at, pr_url) or None to ignore."""
    action = payload.get("action")
    pr = payload.get("pull_request", {})
    branch_name = pr.get("head", {}).get("ref", "")
    pr_url = pr.get("html_url")

    try:
        parts = id_utils.git_branch_to_parts(branch_name)
    except ValueError:
        logger.warning("Unrecognised branch name in webhook: %r", branch_name)
        return None

    request_id = parts["request_id"]

    if action in ("opened", "reopened"):
        return request_id, PullRequestStatus.OPEN, None, pr_url
    if action == "closed" and pr.get("merged"):
        return request_id, PullRequestStatus.MERGED, pr.get("merged_at"), pr_url
    if action == "closed":
        return request_id, PullRequestStatus.CLOSED, None, pr_url

    # assigned, labeled, synchronized, converted_to_draft, etc. — intentionally ignored
    logger.debug("Ignoring pull_request action: %s", action)
    return None



async def _handle_job_pr_event(payload: dict[str, Any]) -> None:
    result = _parse_pr_status(payload)
    if result is None:
        return
    request_id, status, merged_at, pr_url = result
    await apply_pull_request_status(request_id, status, merged_at=merged_at, pull_request_url=pr_url)


async def _handle_review_issue_pr_event(payload: dict[str, Any]) -> None:
    action = payload.get("action")
    if action != "closed":
        return
    pr = payload.get("pull_request", {})
    pr_url = pr.get("html_url")
    issue = await issues_db.get_issue_by_pull_request_url(pr_url)
    if issue is None:
        logger.warning("Webhook: no review issue found for resolution PR %s", pr_url)
        return
    if pr.get("merged"):
        await issues_db.resolve_issue(issue["id"])
        logger.info("Webhook: resolved review issue %s (PR merged)", issue["id"])
    else:
        await issues_db.reopen_issue(issue["id"])
        logger.info("Webhook: reopened review issue %s (PR closed without merge)", issue["id"])


async def _handle_pull_request_event(payload: dict[str, Any]) -> None:
    branch = payload.get("pull_request", {}).get("head", {}).get("ref", "")
    branch_type = branch.split("/")[0] if "/" in branch else None

    match branch_type:
        case "job":
            await _handle_job_pr_event(payload)
        case "resolve":
            await _handle_review_issue_pr_event(payload)
        case _:
            logger.debug("Ignoring PR on unrecognized branch: %r", branch)


def get_router() -> APIRouter:
    router = APIRouter()

    @router.post("")
    async def github_webhook(
        request: Request,
        background_tasks: BackgroundTasks,
        x_github_event: str = Header(...),
        x_hub_signature_256: str = Header(...),
    ):
        env = get_env_vars()
        secret = env.get("GITHUB_WEBHOOK_SECRET")
        if not secret:
            raise HTTPException(status_code=503, detail="Webhook not configured")

        body = await request.body()
        if not _verify_signature(body, secret, x_hub_signature_256):
            logger.warning("GitHub webhook signature verification failed")
            raise HTTPException(status_code=401, detail="Invalid signature")

        logger.info("GitHub webhook received: event=%s", x_github_event)

        if x_github_event == "pull_request":
            content_type = request.headers.get("content-type", "")
            if "application/x-www-form-urlencoded" in content_type:
                payload: dict[str, Any] = json.loads(parse_qs(body.decode())["payload"][0])
            else:
                payload = json.loads(body)
            background_tasks.add_task(_handle_pull_request_event, payload)

        return {"ok": True}

    return router
