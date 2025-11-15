import os

from fastapi import APIRouter, Form, HTTPException, Security, UploadFile

import github_service
import services.auth_service as AuthService
from storage_service import upload_file_to_storage

STORAGE_ENDPOINT = os.getenv("STORAGE_ENDPOINT")
STORAGE_ACCESS_KEY_ID = os.getenv("STORAGE_ACCESS_KEY_ID")
STORAGE_SECRET_ACCESS_KEY = os.getenv("STORAGE_SECRET_ACCESS_KEY")
GITHUB_WORKFLOW_TOKEN = os.getenv("GITHUB_WORKFLOW_TOKEN")


def get_router(api_key_header):
    router = APIRouter()

    @router.post(
        "/github_intake",
        summary="Upload zip file containing municipal data",
        description="Accepts a zip file containing municipal data and processes it",
        include_in_schema=False
    )
    async def github_intake(
        file: UploadFile,
        authorization: str = Security(api_key_header),
        request_id: str = Form(...),
        jurisdiction_id: str = Form(...),
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
        print(f"Processing intake for {request_id} - {jurisdiction_id}")

        zip_file_url = await upload_file_to_storage(
            STORAGE_ENDPOINT,
            STORAGE_ACCESS_KEY_ID,
            STORAGE_SECRET_ACCESS_KEY,
            "crudder",
            file,
            with_presigned_url=True,
        )

        github_service.trigger_github_data_intake_workflow(
            GITHUB_WORKFLOW_TOKEN,
            server_detail["user_email"],
            server_detail["server_url"],
            request_id=request_id,
            jurisdiction_id=jurisdiction_id,
            zip_file_url=zip_file_url,
        )

        return {
            "filename": file.filename,
            "status": "uploaded",
            "zip_file_url": zip_file_url,
            "metadata": {"request_id": request_id, "jurisdiction_id": jurisdiction_id},
        }

    return router
