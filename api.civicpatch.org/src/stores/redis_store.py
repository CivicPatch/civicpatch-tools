import os
import json
import redis
from typing import Optional

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")

redis_client = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

def get(key: str) -> Optional[str]:
    return redis_client.get(key)

def set(key: str, value: str, ttl: int) -> None:
    if ttl > 0:
        redis_client.set(key, value, ex=ttl)

def delete(key: str) -> None:
    redis_client.delete(key)