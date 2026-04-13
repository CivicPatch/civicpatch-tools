import asyncio
import logging
import re
from datetime import date
from typing import Any, Optional
import database.jobs
import database.pull_requests as pull_requests_db
import database.requests
import lib.csv as csv_service
import core.export as requests_export_service
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from schemas.common import Identity, Role, RouteCategory
from lib.auth import require_route_access

logger = logging.getLogger(__name__)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class CreateRegisterRequest(BaseModel):
    request_id: str
    arguments: dict


class PostResultRequest(BaseModel):
    pull_request_url: Optional[str] = None
    data: Optional[Any] = None


def get_router(api_key_header):
    router = APIRouter()

    @router.post(
        "/register",
        summary="Register a new request",
        description="Register a new request in the system.",
        include_in_schema=False,
    )
    async def register_people_job_endpoint(
        request: CreateRegisterRequest,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.MAINTAINERS])),
    ):
        print(
            f"Registering request: {request.request_id} by user {user.provider_user_id} from provider {user.provider}"
        )
        _response = await database.requests.register_request_with_job(
            requested_by_user_id=user.user_id,
            request_id=request.request_id,
            job_type="people",
            arguments_json=request.arguments,
        )
        return {"request_id": request.request_id, "status": "pending"}

    @router.post(
        "/{request_id}/result",
        include_in_schema=False,
    )
    async def post_job_result_endpoint(
        request_id: str,
        request: PostResultRequest,
        user: Identity = Depends(require_route_access(RouteCategory.SERVICE)),
    ):
        errors = []

        tasks = []
        if request.data:  # Called from within civicpatch project
            tasks.append(("result", database.jobs.update_job_data(request_id, request.data)))
        if request.pull_request_url:  # Called from open-data repo
            tasks.append(
                (
                    "pull_request",
                    pull_requests_db.update_job_pull_request_url(
                        request_id, pull_request_url=request.pull_request_url
                    ),
                )
            )

        if tasks:
            results = await asyncio.gather(
                *[t[1] for t in tasks], return_exceptions=True
            )
            for (label, _), result in zip(tasks, results):
                if isinstance(result, Exception):
                    errors.append(f"Failed to update {label}: {result}")
                elif not result:
                    errors.append(f"Failed to update {label}, job may not exist")

        return {"request_id": request_id, "errors": errors}

    @router.get(
        "/export.csv",
        include_in_schema=False,
    )
    async def export_requests_csv(
        state: str = Query(..., description="Two-letter state code, e.g. 'tx'"),
        from_date: Optional[str] = Query(None),
        to_date: Optional[str] = Query(None),
        include_unchanged: bool = Query(False),
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.MAINTAINERS])),
    ):
        if not re.fullmatch(r"[a-z]{2}", state.lower()):
            raise HTTPException(status_code=400, detail="state must be a two-letter code, e.g. 'tx'")
        state = state.lower()
        if from_date and not _DATE_RE.match(from_date):
            raise HTTPException(status_code=400, detail="from_date must be ISO format: YYYY-MM-DD")
        if to_date and not _DATE_RE.match(to_date):
            raise HTTPException(status_code=400, detail="to_date must be ISO format: YYYY-MM-DD")

        requests_data, existing_by_ocdid = await requests_export_service.fetch_export_data(state, from_date, to_date)
        rows = requests_export_service.get_export_rows(requests_data, existing_by_ocdid, include_unchanged)

        filename = f"requests_export_{state}_{date.today().isoformat()}.csv"
        return StreamingResponse(
            csv_service.generate_csv(rows, requests_export_service.CSV_FIELDNAMES),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.get(
        "/people-export.csv",
        include_in_schema=False,
    )
    async def export_people_csv(
        state: str = Query(..., description="Two-letter state code, e.g. 'tx'"),
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.MAINTAINERS])),
    ):
        if not re.fullmatch(r"[a-z]{2}", state.lower()):
            raise HTTPException(status_code=400, detail="state must be a two-letter code, e.g. 'tx'")
        state = state.lower()

        rows = await requests_export_service.fetch_people_export_rows(state)

        filename = f"people_export_{state}_{date.today().isoformat()}.csv"
        return StreamingResponse(
            csv_service.generate_csv(rows, requests_export_service.PEOPLE_CSV_FIELDNAMES),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return router
