from fastapi import APIRouter

import database.coverage as coverage_db


def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("")
    async def get_maps_coverage():
        data = await coverage_db.get_maps_coverage()
        return {"data": data}

    @router.get("/{state}/local")
    async def get_local_status(state: str):
        data = await coverage_db.get_local_status_for_state(state)
        return {"data": data}

    return router
