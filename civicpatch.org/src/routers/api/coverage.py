import time

from fastapi import APIRouter

import lib.cache as cache_service
import database.coverage as coverage_db

CACHE_KEY = "coverage"
CACHE_TTL = 3600  # 1h


def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("")
    async def get_maps_coverage():
        cached = await cache_service.get_cached(CACHE_KEY)
        if cached:
            # cache_service wraps stored data with `expires_at` — strip it before returning
            return {"data": {k: v for k, v in cached.items() if k != "expires_at"}}

        data = await coverage_db.get_maps_coverage()
        await cache_service.set_cached(CACHE_KEY, data, time.time() + CACHE_TTL)
        return {"data": data}

    @router.get("/{state}/local")
    async def get_local_status(state: str):
        cache_key = f"coverage:local:{state}"
        cached = await cache_service.get_cached(cache_key)
        if cached:
            return {"data": {k: v for k, v in cached.items() if k != "expires_at"}}

        data = await coverage_db.get_local_status_for_state(state)
        await cache_service.set_cached(cache_key, data, time.time() + CACHE_TTL)
        return {"data": data}

    return router
