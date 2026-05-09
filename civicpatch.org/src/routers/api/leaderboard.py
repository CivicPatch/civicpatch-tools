import time

from fastapi import APIRouter

import lib.cache as cache_service
import database.review_session_stats as review_session_stats_db

LEADERBOARD_CACHE_KEY = "leaderboard_data"
LEADERBOARD_CACHE_TTL = 3600  # 1 hour


def get_router():
    router = APIRouter()

    @router.get("")
    async def get_leaderboard():
        cached = await cache_service.get_cached(LEADERBOARD_CACHE_KEY)
        if cached:
            return {"data": cached}

        rows = await review_session_stats_db.get_leaderboard()
        data = {"entries": rows}
        await cache_service.set_cached(
            LEADERBOARD_CACHE_KEY, data, time.time() + LEADERBOARD_CACHE_TTL
        )
        return {"data": data}

    return router
