import asyncio
import json
import traceback
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from interfaces.schemas import (
    PeopleCollectorJobRequest,
    validate_people_request
)
from jobs.people_collector.main import start_threaded as start_people_collector
from jobs.people_collector.main import stop as stop_people_collector
from jobs.people_collector.schemas import WorkflowStatus
from shared.utils import id_utils
from jobs.registry import get_workflow
import services.civicpatch_api


def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("/permissions")
    async def get_permissions(request: Request):
        data = await services.civicpatch_api.get_me(request)
        authenticated = data.get("authenticated", False)

        PERMISSIONS = {
            "can_scrape_local": services.civicpatch_api.can_scrape_locally,
            "can_scrape_remote": "maintainers" in data.get("teams", []),
            "can_view_jurisdiction_page": len(data.get("teams", [])) > 0
        }

        return {
            "permissions": PERMISSIONS, 
            "authenticated": authenticated, 
            "data": data
        }

    @router.post("/pipelines")
    async def post_pipelines(
        request: PeopleCollectorJobRequest,
        background_tasks: BackgroundTasks,
    ):
        if not services.civicpatch_api.can_scrape_locally:
            raise HTTPException(status_code=403, detail="Local scraping is not allowed for this user")

        request_id = id_utils.make_request_id()
        warnings, errors = validate_people_request(request)

        background_tasks.add_task(
            start_people_collector,
            request_id, 
            request.jurisdiction_ocdid, 
            request.config
        )

        if errors:
            raise HTTPException(status_code=400, detail={"errors": errors, "warnings": warnings})

        return {
            "data": {
                "request_id": request_id,
                "jurisdiction_ocdid": request.jurisdiction_ocdid,
                "message": "Workflow started"
            }
        }

    @router.post("/pipelines/stop")
    async def stop_pipeline_endpoint(
        jurisdiction_ocdid: str,
    ):
        if not services.civicpatch_api.can_scrape_locally:
            raise HTTPException(status_code=403, detail="Local scraping is not allowed for this user")

        workflow = get_workflow(jurisdiction_ocdid)
        if workflow is None:
            raise HTTPException(status_code=404, detail="Workflow not found")

        stop_people_collector(jurisdiction_ocdid) 
        return {"status": "stopping", "jurisdiction_ocdid": jurisdiction_ocdid}

    return router
