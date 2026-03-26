import asyncio
import json
import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CreateRegisterRequest(BaseModel):
    request_id: str
    arguments: dict


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
            _response = await databas.requests.register(
                requested_by_user_id=user.id,
                request_id=request.request_id,
                request_type="people",
                arguments_json=request.arguments,
            )
            return {"request_id": request.request_id, "status": "pending"}


    return router
