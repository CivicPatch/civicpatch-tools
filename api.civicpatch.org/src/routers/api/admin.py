from fastapi import APIRouter, BackgroundTasks

import services.github.data_sync_service
import services.github.pull_request_sync_service
from schemas.requests import OdSyncRequestSchema

def get_router() -> APIRouter:
    router = APIRouter()

    @router.post("/od_sync", include_in_schema=False)
    async def bulk_sync_endpoint(
        request: OdSyncRequestSchema,
        background_tasks: BackgroundTasks,
    ):
        background_tasks.add_task(services.github.data_sync_service.sync, request)

        return {"status": "running"}

    @router.post("/pr_sync", include_in_schema=False)
    async def pr_sync_endpoint(background_tasks: BackgroundTasks):
        background_tasks.add_task(services.github.pull_request_sync_service.sync_open_pr_state)
        return {"status": "running"}

    return router
