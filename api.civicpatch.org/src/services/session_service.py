import time
import json
from typing import Optional

from stores import redis_store

SESSION_PREFIX = "session:"

def _key(user_id: str) -> str:
    return f"{SESSION_PREFIX}{user_id}"

def create(user_id: str, token: str, expires_at: float) -> None:
    ttl = int(expires_at - time.time())
    if ttl <= 0:
        return
    entry = {"token": token, "expires_at": expires_at}
    redis_store.set(_key(user_id), json.dumps(entry), ttl)

def get(user_id: str) -> Optional[str]:
    raw = redis_store.get(_key(user_id))
    if not raw:
        return None
    data = json.loads(raw)
    if time.time() >= data.get("expires_at", 0):
        return None
    return data["token"]

def invalidate(user_id: str) -> None:
    redis_store.delete(_key(user_id))