import json
from typing import Any, Optional

import lib.redis as redis_store

DEFAULT_TTL_SECONDS = 3600


async def get_cached(key: str) -> Optional[Any]:
    raw = await redis_store.get(key)
    return json.loads(raw) if raw else None


async def set_cached(key: str, value: Any, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
    await redis_store.set(key, json.dumps(value), ttl_seconds)


async def invalidate(key: str) -> None:
    await redis_store.delete(key)
