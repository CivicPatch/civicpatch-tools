import os
import redis
from typing import Optional

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")

redis_client = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

# Cache Services 

def get(key: str) -> Optional[str]:
    """Get a value from Redis by key."""
    if not key:
        raise ValueError("Key cannot be empty")
    
    try:
        return redis_client.get(key)
    except redis.RedisError as e:
        raise RuntimeError(f"Failed to get key '{key}': {str(e)}")

def set(key: str, value: str, ttl: Optional[int] = None) -> None:
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
            redis_client.set(key, value, ex=ttl)
        else:
            redis_client.set(key, value)
    except redis.RedisError as e:
        raise RuntimeError(f"Failed to set key '{key}': {str(e)}")

def delete(key: str) -> None:
    """Delete a key from Redis."""
    if not key:
        raise ValueError("Key cannot be empty")
    
    try:
        redis_client.delete(key)
    except redis.RedisError as e:
        raise RuntimeError(f"Failed to delete key '{key}': {str(e)}")

# Pub/Sub Services
def publish(channel: str, message: str) -> None:
    """Publish a message to a Redis pub/sub channel."""
    if not channel:
        raise ValueError("Channel cannot be empty")
    
    try:
        redis_client.publish(channel, message)
    except redis.RedisError as e:
        raise RuntimeError(f"Failed to publish to channel '{channel}': {str(e)}")

def subscribe(channel: str):
    """Subscribe to a Redis pub/sub channel and yield messages."""
    if not channel:
        raise ValueError("Channel cannot be empty")
    
    pubsub = redis_client.pubsub()
    pubsub.subscribe(channel)
    try:
        for message in pubsub.listen():
            if message["type"] == "message":
                yield message["data"]
    except redis.RedisError as e:
        raise RuntimeError(f"Failed to subscribe to channel '{channel}': {str(e)}")
    finally:
        pubsub.unsubscribe(channel)
        pubsub.close()

def unsubscribe(channel: str) -> None:
    """Unsubscribe from a Redis pub/sub channel."""
    if not channel:
        raise ValueError("Channel cannot be empty")
    
    try:
        pubsub = redis_client.pubsub()
        pubsub.unsubscribe(channel)
        pubsub.close()
    except redis.RedisError as e:
        raise RuntimeError(f"Failed to unsubscribe from channel '{channel}': {str(e)}")