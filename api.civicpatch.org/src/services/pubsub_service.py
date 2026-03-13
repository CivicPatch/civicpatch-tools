import asyncio
import json
import logging
import time
from typing import AsyncGenerator

from stores import redis_store

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 15  # seconds


async def publish(channel: str, message: str) -> None:
    """Publish a message to a Redis pub/sub channel."""
    await redis_store.publish(channel, message)


async def subscribe(channel: str) -> AsyncGenerator[str, None]:
    """Subscribe to a Redis pub/sub channel and yield messages."""
    pubsub = redis_store.pubsub()
    await pubsub.subscribe(channel)
    last_heartbeat = time.time()
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"]
                yield data.decode("utf-8") if isinstance(data, bytes) else data
                last_heartbeat = time.time()
            else:
                if time.time() - last_heartbeat >= HEARTBEAT_INTERVAL:
                    yield ": heartbeat\n"
                    last_heartbeat = time.time()
                await asyncio.sleep(0.1)
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
