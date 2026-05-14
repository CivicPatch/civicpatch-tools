import hashlib
import hmac
import logging

from core.blog_sync import SyncCollisionError, sync_blog_posts
from environment import get_env_vars
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import ValidationError
from schemas.webhooks.blog_sync import BlogSyncPayload

logger = logging.getLogger(__name__)


def _verify_signature(body: bytes, secret: str, signature: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def get_router() -> APIRouter:
    router = APIRouter()

    @router.post("")
    async def blog_sync_webhook(
        request: Request,
        x_signature_sha256: str = Header(...),
    ):
        env = get_env_vars()
        secret = env.get("BLOG_SYNC_WEBHOOK_SECRET")
        if not secret:
            raise HTTPException(status_code=503, detail="Webhook not configured")

        body = await request.body()
        if not _verify_signature(body, secret, x_signature_sha256):
            logger.warning("Blog sync webhook: signature verification failed")
            raise HTTPException(status_code=401, detail="Invalid signature")

        try:
            payload = BlogSyncPayload.model_validate_json(body)
        except ValidationError as e:
            logger.warning("Blog sync webhook: invalid payload: %s", e)
            raise HTTPException(status_code=422, detail="Invalid payload")

        try:
            result = await sync_blog_posts(payload)
        except SyncCollisionError as e:
            logger.error("Blog sync aborted: %s", e)
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "slug_collision",
                    "slug": e.slug,
                    "discussion_numbers": e.numbers,
                },
            )

        if result.skipped:
            logger.warning("Blog sync partial: skipped=%s", result.skipped)
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "partial_sync",
                    "synced": result.synced,
                    "skipped": result.skipped,
                },
            )

        logger.info("Blog sync ok: synced=%s", result.synced)
        return {"synced": result.synced}

    return router
