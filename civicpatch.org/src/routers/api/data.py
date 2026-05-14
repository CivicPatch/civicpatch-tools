from fastapi import APIRouter

import database.dashboard as dashboard_db
import lib.cache as cache_service

DASHBOARD_CACHE_KEY = "dashboard_data"
DASHBOARD_CACHE_TTL = 86400  # 1 day


def get_router():
    router = APIRouter()

    @router.get("/dashboard")
    async def get_dashboard_data():
        cached = await cache_service.get_cached(DASHBOARD_CACHE_KEY)
        if cached:
            return {"data": cached}

        data = await dashboard_db.get_dashboard()
        if data and data.get("states"):
            await cache_service.set_cached(DASHBOARD_CACHE_KEY, data, DASHBOARD_CACHE_TTL)
        return {"data": data}

    return router
