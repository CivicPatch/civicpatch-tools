import hashlib
import hmac
import json
import logging
from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

import shared.utils.id_utils as id_utils
from shared.utils.statuses import PullRequestStatus
from database.database import update_job_pull_request_status
import database.review_sessions as review_sessions_db
from environment import get_env_vars
from services.github.pull_request_sync_service import register_and_sync_pr_job

logger = logging.getLogger(__name__)


def _verify_signature(body: bytes, secret: str, signature: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _parse_pr_status(payload: dict[str, Any]) -> tuple[str, str, str, str | None, str | None] | None:
    """Returns (request_id, jurisdiction_ocdid, status, merged_at, pr_url) or None to ignore."""
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
    jurisdiction_ocdid = parts["jurisdiction_ocdid"]

    if action in ("opened", "reopened"):
        return request_id, jurisdiction_ocdid, PullRequestStatus.OPEN, None, pr_url
    if action == "closed" and pr.get("merged"):
        return request_id, jurisdiction_ocdid, PullRequestStatus.MERGED, pr.get("merged_at"), pr_url
    if action == "closed":
        return request_id, jurisdiction_ocdid, PullRequestStatus.CLOSED, None, pr_url

    # assigned, labeled, synchronized, converted_to_draft, etc. — intentionally ignored
    logger.debug("Ignoring pull_request action: %s", action)
    return None



async def _handle_pull_request_event(payload: dict[str, Any]):
    result = _parse_pr_status(payload)
    if result is None:
        return
    request_id, jurisdiction_ocdid, status, merged_at, pr_url = result
    updated = await update_job_pull_request_status(request_id, status, merged_at, pull_request_url=pr_url)
    if status in (PullRequestStatus.MERGED, PullRequestStatus.CLOSED):
        await review_sessions_db.resolve_review_session_entries_by_request_id(request_id)
    if not updated and status == PullRequestStatus.OPEN:
        logger.info("Webhook: no job found for %s, creating", request_id)
        await register_and_sync_pr_job(request_id, jurisdiction_ocdid, pr_url, provider="github_webhook")


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
