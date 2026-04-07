import asyncio
import json
import logging
import traceback
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from interfaces.api.routes.frontend import build_permissions
from interfaces.schemas import (
    PeopleCollectorJobRequest,
    validate_people_request
)
from jobs.people_collector.main import start_threaded as start_people_collector
from jobs.people_collector.schemas import WorkflowStatus
from jobs.engine import WorkflowError
from shared.utils import id_utils
import services.civicpatch_api

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("/permissions")
    async def get_permissions(request: Request):
        data = await services.civicpatch_api.get_me(request)
        return {
            "permissions": build_permissions(data),
            "authenticated": data.get("authenticated", False),
            "data": data
        }

    async def _run_pipeline(request_id, jurisdiction_ocdid, config):
        try:
            await start_people_collector(request_id, jurisdiction_ocdid, config)
        except Exception:
            pass  # Already logged in people_collector.main

    @router.post("/pipelines")
    async def post_pipelines(
        request: PeopleCollectorJobRequest,
        background_tasks: BackgroundTasks,
        http_request: Request,
    ):
        if request.scrape_mode == "remote":
            me = await services.civicpatch_api.get_me(http_request)
            if "maintainers" not in me.get("teams", []):
                raise HTTPException(status_code=403, detail="Remote scraping requires maintainer access")
        else:
            if not services.civicpatch_api.can_scrape_locally():
                raise HTTPException(status_code=403, detail="Local scraping is not allowed for this user")

        request_id = id_utils.make_request_id()
        warnings, errors = validate_people_request(request)

        if errors:
            raise HTTPException(status_code=400, detail={"errors": errors, "warnings": warnings})

        background_tasks.add_task(
            _run_pipeline,
            request_id, 
            request.jurisdiction_ocdid, 
            request.config
        )

        return {
            "data": {
                "request_id": request_id,
                "jurisdiction_ocdid": request.jurisdiction_ocdid,
                "message": "Workflow started"
            }
        }

    return router
