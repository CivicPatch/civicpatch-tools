import logging
import re
from datetime import date
import database.pipeline_runs
import database.requests
import lib.csv as csv_service
import services.people_csv_export as requests_export_service
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from schemas.common import Identity, UserRole, RouteCategory
from schemas.pipeline_runs import CreateRegisterRequest
from lib.auth import require_route_access

logger = logging.getLogger(__name__)



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
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)),
    ):
        print(
            f"Registering request: {request.request_id} by user {user.provider_user_id} from provider {user.provider}"
        )
        _response = await database.requests.register_request_with_pipeline_run(
            requested_by_user_id=user.user_id,
            request_id=request.request_id,
            job_type="people",
            arguments_json=request.arguments,
        )
        return {"request_id": request.request_id, "status": "pending"}

    @router.get(
        "/people-export.csv",
        include_in_schema=False,
    )
    async def export_people_csv(
        state: str = Query(..., description="Two-letter state code, e.g. 'tx'"),
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)),
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
