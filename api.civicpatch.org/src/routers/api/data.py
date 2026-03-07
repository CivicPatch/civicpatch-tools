from fastapi import APIRouter, HTTPException
from services import github_service, cache_service
import json
import time

router = APIRouter()
DASHBOARD_PATH = "scripts/track_progress/data/dashboard.json"
DASHBOARD_CACHE_KEY = "dashboard_data"
DASHBOARD_CACHE_TTL = 86400  # 1 day

def get_router():
    router = APIRouter()

    @router.get("/dashboard")
    async def get_dashboard_data():
        # Try cache first
        cached = cache_service.get_cached(DASHBOARD_CACHE_KEY)
        if cached:
            return {"data": cached}

        # Fetch from GitHub if not cached
        file_content = await github_service.get_github_file_contents(DASHBOARD_PATH, ref="main")
        if not file_content:
            raise HTTPException(status_code=404, detail="Dashboard data not found")
        try:
            data = json.loads(file_content)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error parsing dashboard.json: {e}")

        cache_service.set_cached(DASHBOARD_CACHE_KEY, data, time.time() + DASHBOARD_CACHE_TTL)
        return {"data": data}
    
    return router