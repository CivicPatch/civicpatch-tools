from fastapi import APIRouter

import database.coverage as coverage_db
import services.coverage as coverage_service


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

    @router.get("/{state}/summary")
    async def get_state_summary(state: str):
        data = await coverage_service.get_state_coverage(state)
        return {"data": data}

    @router.get("/{state}/municipalities")
    async def get_municipalities(state: str):
        data = await coverage_service.get_municipality_list(state)
        return {"data": data}

    return router
