import os
import logging

from fastapi import APIRouter, Form, HTTPException, Security, UploadFile, BackgroundTasks

import services.auth_service as AuthService
import job_service.people_collector
from schemas.requests import HandleSubmitJobArtifactsRequest
from schemas.responses import SubmitJobArtifactsResponse

GITHUB_WORKFLOW_TOKEN = os.getenv("GITHUB_WORKFLOW_TOKEN")

logger = logging.getLogger(__name__)

def get_router(api_key_header):
    router = APIRouter()

    @router.post(
        "/submit_job_artifacts",
        summary="Upload zip file containing municipal data",
        description="Accepts a zip file containing municipal data and processes it",
        include_in_schema=False
    )
    async def intake_endpoint(
        file: UploadFile,
        background_tasks: BackgroundTasks,
        authorization: str = Security(api_key_header),
        request_id: str = Form(...),
        jurisdiction_ocdid: str = Form(...),
    ):
        if not authorization:
            raise HTTPException(status_code=401, detail="Missing Authorization header")

        api_key = authorization.strip()
        server_detail, error_string = await AuthService.is_authorized(api_key)
        if error_string:
            raise HTTPException(status_code=401, detail=error_string)

        # Check file type
        if not file.filename.lower().endswith(".zip"):
            raise HTTPException(status_code=400, detail="Only .zip files are accepted")
        if file.content_type not in ["application/zip", "application/x-zip-compressed"]:
            raise HTTPException(
                status_code=400, detail="Invalid content type for zip file"
            )

        # Now you have access to the parameters
        logger.info(f"Processing intake for {request_id} - {jurisdiction_ocdid}")
        request = HandleSubmitJobArtifactsRequest(
            file=file,
            request_id=request_id,
            jurisdiction_ocdid=jurisdiction_ocdid,
            server_detail=server_detail
        )

        response = await job_service.people_collector.handle_submit_job_artifacts(
            request=request,
            background_tasks=background_tasks
        )

        return response

    return router
