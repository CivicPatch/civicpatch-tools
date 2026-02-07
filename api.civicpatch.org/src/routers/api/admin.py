from fastapi import APIRouter, BackgroundTasks, HTTPException, Security

from pydantic import BaseModel
from typing import List, Optional
import services.github_sync_service

class OdSyncRequestSchema(BaseModel):
    states: List[str] = None
    jurisdiction_ocdids: Optional[List[str]] = None

def get_router(api_key_header, pool) -> APIRouter:
    router = APIRouter()

    @router.post("/od_sync", include_in_schema=False)
    async def sync_people_endpoint(
        request: OdSyncRequestSchema,
        background_tasks: BackgroundTasks,
    ):
        background_tasks.add_task(services.github_sync_service.data, request.states, request.jurisdiction_ocdids)

        return {"status": "running"}
    
    return router