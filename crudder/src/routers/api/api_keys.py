from fastapi import APIRouter, Request, Depends

import database
from utils.auth import get_user 
from schemas import Identity


def get_router():
    router = APIRouter()

    @router.post("", include_in_schema=False)
    async def create_api_key_endpoint(
        request: Request,
        user: Identity = Depends(get_user)
    ):
        api_key = await database.create_api_key(user.provider, user.provider_user_id)

        return {
            "status": "success",
            "message": "API key created successfully.",
            "api_key": api_key,
        }

    @router.delete("/{api_key_id}", include_in_schema=False)
    async def delete_api_key(
        request: Request,
        api_key_id: str,
        _user: Identity = Depends(get_user)
    ):
        # TODO: double check auth
        await database.revoke_api_key(api_key_id)

    return router
