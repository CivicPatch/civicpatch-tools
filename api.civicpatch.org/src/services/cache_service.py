import os
import time
import json
import redis
from typing import Optional, TypedDict

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")

class CachedToken(TypedDict, total=False):
    token: str
    expires_at: float

EXPIRY_BUFFER_SECONDS = 300
DEFAULT_CACHE_SECONDS = 3600  # 1 hour

# Connect to Redis (adjust host/port/db as needed)
redis_client = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

def get_cached(key: str):
    raw = redis_client.get(key)
    if not raw:
        return None
    cached = json.loads(raw)
    expires_at = cached.get("expires_at")
    if expires_at is not None and time.time() >= expires_at - EXPIRY_BUFFER_SECONDS:
        return None
    return cached["token"]

def set_cached(key: str, value: str, expires_at: Optional[float] = None):
    if expires_at is None:
        expires_at = time.time() + DEFAULT_CACHE_SECONDS
    entry: CachedToken = {"token": value, "expires_at": expires_at}
    ttl = int(expires_at - time.time())
    redis_client.set(key, json.dumps(entry), ex=ttl)

def invalidate_token(key: str) -> None:
    redis_client.delete(key)