from fastapi import APIRouter, Depends, HTTPException, Request
from psycopg.errors import UniqueViolation
from pydantic import BaseModel

import database.users as database
from schemas.common import Identity, Username
from lib.auth import get_user


class UsernameUpdateRequest(BaseModel):
    username: Username


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

    @router.post("/username")
    async def set_username(
        body: UsernameUpdateRequest,
        user: Identity = Depends(get_user),
    ):
        if not user.user_id:
            raise HTTPException(status_code=401, detail="User ID not available")
        try:
            await database.set_username(user.user_id, body.username)
        except UniqueViolation:
            raise HTTPException(status_code=409, detail="That name is already taken")
        return {"data": {"username": body.username}}

    return router
