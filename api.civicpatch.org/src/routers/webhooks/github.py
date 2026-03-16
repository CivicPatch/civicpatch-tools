import hashlib
import hmac
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

import shared.utils.id_utils as id_utils
from database.database import update_job_pull_request_status
from environment import get_env_vars

logger = logging.getLogger(__name__)


def _verify_signature(body: bytes, secret: str, signature: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _parse_pr_status(payload: dict[str, Any]) -> tuple[str, str, str | None] | None:
    action = payload.get("action")
    pr = payload.get("pull_request", {})
    branch_name = pr.get("head", {}).get("ref", "")

    try:
        parts = id_utils.git_branch_to_parts(branch_name)
    except ValueError:
        logger.warning("Unrecognised branch name in webhook: %r", branch_name)
        return None

    request_id = parts["request_id"]

    if action in ("opened", "reopened"):
        return request_id, "open", None
    if action == "closed" and pr.get("merged"):
        return request_id, "merged", pr.get("merged_at")
    if action == "closed":
        return request_id, "closed", None

    # assigned, labeled, synchronized, converted_to_draft, etc. — intentionally ignored
    logger.debug("Ignoring pull_request action: %s", action)
    return None


async def _handle_pull_request_event(payload: dict[str, Any]):
    result = _parse_pr_status(payload)
    if result is None:
        return
    request_id, status, merged_at = result
    await update_job_pull_request_status(request_id, status, merged_at)


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
            raise HTTPException(status_code=401, detail="Invalid signature")

        if x_github_event == "pull_request":
            payload: dict[str, Any] = await request.json()
            background_tasks.add_task(_handle_pull_request_event, payload)

        return {"ok": True}

    return router
