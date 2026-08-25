from typing import Optional

import redis.asyncio as redis

from environment import get_env_vars
env = get_env_vars()

REDIS_HOST = env["REDIS_HOST"]

redis_client = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

PUB_SUB_TIMEOUT = 1.0


async def get(key: str) -> Optional[str]:
    """Get a value from Redis by key."""
    if not key:
        raise ValueError("Key cannot be empty")

    try:
        return await redis_client.get(key)
    except redis.RedisError as e:
        raise RuntimeError(f"Failed to get key '{key}': {str(e)}")


async def set(key: str, value: str, ttl: Optional[int] = None) -> None:
    """
    Set a key-value pair in Redis.

    Args:
        key: Redis key
        value: Value to store
        ttl: Time to live in seconds. If None, key persists indefinitely.
    """
    if not key:
        raise ValueError("Key cannot be empty")

    try:
        if ttl is not None:
            if ttl <= 0:
                raise ValueError("TTL must be a positive integer")
            await redis_client.set(key, value, ex=ttl)
        else:
            await redis_client.set(key, value)
    except redis.RedisError as e:
        raise RuntimeError(f"Failed to set key '{key}': {str(e)}")


async def delete(key: str) -> None:
    """Delete a key from Redis."""
    if not key:
        raise ValueError("Key cannot be empty")

    try:
        await redis_client.delete(key)
    except redis.RedisError as e:
        raise RuntimeError(f"Failed to delete key '{key}': {str(e)}")


# Pub/Sub Services
def pubsub():
    return redis_client.pubsub()


async def publish(channel: str, message: str) -> None:
    """Publish a message to a Redis pub/sub channel."""
    if not channel:
        raise ValueError("Channel cannot be empty")

    try:
        await redis_client.publish(channel, message)
    except redis.RedisError as e:
        raise RuntimeError(f"Failed to publish to channel '{channel}': {str(e)}")


async def subscribe(channel: str):
    """Subscribe to a Redis pub/sub channel and yield messages."""
    if not channel:
        raise ValueError("Channel cannot be empty")

    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel)
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                yield message["data"]
    except redis.RedisError as e:
        raise RuntimeError(f"Failed to subscribe to channel '{channel}': {str(e)}")
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()


async def unsubscribe(channel: str) -> None:
    """Unsubscribe from a Redis pub/sub channel."""
    if not channel:
        raise ValueError("Channel cannot be empty")

    try:
        pubsub = redis_client.pubsub()
        await pubsub.unsubscribe(channel)
        await pubsub.close()
    except redis.RedisError as e:
        raise RuntimeError(f"Failed to unsubscribe from channel '{channel}': {str(e)}")


async def get_message(
    ignore_subscribe_messages: bool = True, timeout: Optional[float] = None
):
    """Get a message from the Redis pub/sub channel."""
    try:
        message = await redis_client.pubsub().get_message(
            ignore_subscribe_messages=ignore_subscribe_messages,
            timeout=timeout or PUB_SUB_TIMEOUT,
        )
        return message
    except redis.RedisError as e:
        raise RuntimeError(f"Failed to get message: {str(e)}")
