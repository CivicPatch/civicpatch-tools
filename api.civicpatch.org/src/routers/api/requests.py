import asyncio
import json
import logging
import time
from typing import Any, Optional
import database.database
import database.requests

logger = logging.getLogger(__name__)


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
            _response = await database.requests.register(
                requested_by_user_id=user.id,
                request_id=request.request_id,
                request_type="people",
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
            tasks.append(("result", database.database.update_job_data(request_id, request.data)))
        if request.pull_request_url:  # Called from open-data repo
            tasks.append(
                (
                    "pull_request",
                    database.database.update_job_pull_request_url(
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

    return router
