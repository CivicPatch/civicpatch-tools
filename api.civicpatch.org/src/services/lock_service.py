from stores import redis_store


async def acquire_lock(key: str, ttl: int) -> bool:
    result = await redis_store.redis_client.set(key, "1", nx=True, ex=ttl)
    return result is True


async def release_lock(key: str) -> None:
    await redis_store.delete(key)
