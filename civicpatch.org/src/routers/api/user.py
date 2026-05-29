from fastapi import APIRouter, Depends, HTTPException, Request
from psycopg.errors import UniqueViolation
from pydantic import BaseModel

import database.users as database
import lib.usernames as usernames
from schemas.common import Identity
from lib.auth import get_user

_MAX_DISPLAY_NAME_LENGTH = 50


class DisplayNameUpdateRequest(BaseModel):
    display_name: str


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

    @router.get("/display-name/suggestion")
    async def get_display_name_suggestion():
        candidate = usernames.pick_two_words()
        if not await database.display_name_in_use(candidate):
            return {"data": candidate}
        candidate = usernames.append_place(candidate)
        if not await database.display_name_in_use(candidate):
            return {"data": candidate}
        return {"data": usernames.append_numeric_suffix(candidate)}

    @router.post("/display-name")
    async def set_display_name(
        body: DisplayNameUpdateRequest,
        user: Identity = Depends(get_user),
    ):
        value = body.display_name.strip()
        if not value:
            raise HTTPException(status_code=400, detail="display_name cannot be empty")
        if len(value) > _MAX_DISPLAY_NAME_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=f"display_name too long (max {_MAX_DISPLAY_NAME_LENGTH})",
            )
        if not user.user_id:
            raise HTTPException(status_code=401, detail="User ID not available")
        try:
            await database.set_user_display_name(user.user_id, value)
        except UniqueViolation:
            raise HTTPException(status_code=409, detail="That name is already taken")
        return {"data": {"display_name": value}}

    return router
