from fastapi import APIRouter, BackgroundTasks

import services.github_sync_service
from schemas.requests import OdSyncRequestSchema

def get_router() -> APIRouter:
    router = APIRouter()

    @router.post("/od_sync", include_in_schema=False)
    async def bulk_sync_endpoint(
        request: OdSyncRequestSchema,
        background_tasks: BackgroundTasks,
    ):
        background_tasks.add_task(services.github_sync_service.sync, request)

        return {"status": "running"}
    
    return router
