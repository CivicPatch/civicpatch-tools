from fastapi import APIRouter, Depends, Request

import database.users as database
from schemas.common import Identity
from lib.auth import get_user


def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("/usage")
    async def get_user_api_usage_endpoint(
        request: Request,
        user: Identity = Depends(get_user),
    ):
        usage = await database.get_api_usage_for_user(
            user.provider, user.provider_user_id
        )
        return {"api_usage": usage}
    
    return router
