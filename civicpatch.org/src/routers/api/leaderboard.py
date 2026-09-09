from fastapi import APIRouter

import lib.cache as cache_service
import database.review_session_stats as review_session_stats_db
from schemas.common import LeaderboardPeriod

LEADERBOARD_CACHE_KEY_PREFIX = "leaderboard_data"
LEADERBOARD_CACHE_TTL = 3600  # 1 hour


def get_router():
    router = APIRouter()

    @router.get("")
    async def get_leaderboard(period: LeaderboardPeriod = LeaderboardPeriod.ALL_TIME):
        cache_key = f"{LEADERBOARD_CACHE_KEY_PREFIX}:{period.value}"
        cached = await cache_service.get_cached(cache_key)
        if cached:
            return {"data": cached}

        rows = await review_session_stats_db.get_leaderboard(period)
        data = {"entries": rows}
        await cache_service.set_cached(cache_key, data, LEADERBOARD_CACHE_TTL)
        return {"data": data}

    return router
