import time
from typing import Callable, Awaitable, Optional, TypedDict


class CachedToken(TypedDict):
    token: str
    expires_at: float


# Simple cache: just get/set/invalidate
_store: dict[str, CachedToken] = {}

EXPIRY_BUFFER_SECONDS = 300

def get_cached(key: str):
    cached = _store.get(key)
    if cached and time.time() < cached["expires_at"] - 300:
        return cached["token"]
    return None

def set_cached(key: str, value: str, expires_at: float):
    _store[key] = {"token": value, "expires_at": expires_at}

def invalidate_token(key: str) -> None:
    """Force a token to be refreshed on next request."""
    _store.pop(key, None)