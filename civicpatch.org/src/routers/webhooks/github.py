import hashlib
import hmac
import logging

from fastapi import APIRouter, Header, HTTPException, Request

from environment import get_env_vars

logger = logging.getLogger(__name__)


def _verify_signature(body: bytes, secret: str, signature: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def get_router() -> APIRouter:
    router = APIRouter()

    @router.post("")
    async def github_webhook(
        request: Request,
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

        # Nothing is dispatched on. The `resolve/` PR handler went with `pr_opened`: nothing
        # opened those PRs, so nothing could ever match one. The route stays so GitHub's
        # configured webhook keeps getting a 200 rather than a 404.
        return {"ok": True}

    return router
