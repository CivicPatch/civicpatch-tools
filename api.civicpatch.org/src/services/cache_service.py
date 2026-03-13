import json
import time
from typing import Optional

from stores import redis_store

EXPIRY_BUFFER_SECONDS = 300
DEFAULT_CACHE_SECONDS = 3600


async def get_cached(key: str) -> Optional[dict]:
    raw = await redis_store.get(key)
    if not raw:
        return None
    cached = json.loads(raw)
    expires_at = cached.get("expires_at")
    if expires_at is not None and time.time() >= expires_at - EXPIRY_BUFFER_SECONDS:
        return None
    # Return the whole cached dictionary (excluding expires_at if you want)
    return cached


async def set_cached(key: str, value: dict, expires_at: Optional[float] = None) -> None:
    if expires_at is None:
        expires_at = time.time() + DEFAULT_CACHE_SECONDS
    entry = dict(value)  # Make a copy to avoid mutating input
    entry["expires_at"] = expires_at
    ttl = int(expires_at - time.time())
    await redis_store.set(key, json.dumps(entry), ttl)


async def invalidate(key: str) -> None:
    await redis_store.delete(key)
