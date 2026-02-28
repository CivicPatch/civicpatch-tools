import time
from typing import Callable, Awaitable, Optional, TypedDict


class CachedToken(TypedDict):
    token: str
    expires_at: float


# In-memory store (swap out for Redis later)
_store: dict[str, CachedToken] = {}

EXPIRY_BUFFER_SECONDS = 300


def _is_valid(cached: Optional[CachedToken]) -> bool:
    return cached is not None and time.time() < cached["expires_at"] - EXPIRY_BUFFER_SECONDS


async def get_cached_token(
    key: str,
    fetch_token: Callable[[], Awaitable[tuple[str, float]]],
) -> str:
    """
    Get a cached token by key, or fetch a new one if missing/expired.

    Args:
        key: Cache key (e.g. "github:installation:12345")
        fetch_token: Async callable that returns (token, expires_at_unix_timestamp)

    Returns:
        A valid token string
    """
    cached = _store.get(key)

    if _is_valid(cached):
        return cached["token"]

    token, expires_at = await fetch_token()
    _store[key] = CachedToken(token=token, expires_at=expires_at)

    return token


def invalidate_token(key: str) -> None:
    """Force a token to be refreshed on next request."""
    _store.pop(key, None)