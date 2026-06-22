from fastapi import APIRouter

import database.dashboard as dashboard_db


def get_router():
    router = APIRouter()

    @router.get("/dashboard")
    async def get_dashboard_data():
        data = await dashboard_db.get_dashboard()
        return {"data": data}

    return router
