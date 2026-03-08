import time
import json
from typing import Optional

from stores import redis_store

EXPIRY_BUFFER_SECONDS = 300
DEFAULT_CACHE_SECONDS = 3600

def get_cached(key: str) -> Optional[str]:
    raw = redis_store.get(key)
    if not raw:
        return None
    cached = json.loads(raw)
    expires_at = cached.get("expires_at")
    if expires_at is not None and time.time() >= expires_at - EXPIRY_BUFFER_SECONDS:
        return None
    return cached["token"]

def set_cached(key: str, value: str, expires_at: Optional[float] = None) -> None:
    if expires_at is None:
        expires_at = time.time() + DEFAULT_CACHE_SECONDS
    entry = {"token": value, "expires_at": expires_at}
    ttl = int(expires_at - time.time())
    redis_store.set(key, json.dumps(entry), ttl)

def invalidate(key: str) -> None:
    redis_store.delete(key)