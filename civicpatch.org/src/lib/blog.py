import json

import lib.redis as redis_store
from schemas.blog import BlogIndexEntry, BlogPost

INDEX_KEY = "blog:index"
POST_KEY_PREFIX = "blog:post:"


async def get_all_posts() -> list[BlogIndexEntry]:
    raw = await redis_store.get(INDEX_KEY)
    if not raw:
        return []
    return [BlogIndexEntry.model_validate(e) for e in json.loads(raw)]


async def get_post(slug: str) -> BlogPost | None:
    raw = await redis_store.get(f"{POST_KEY_PREFIX}{slug}")
    if not raw:
        return None
    return BlogPost.model_validate_json(raw)
