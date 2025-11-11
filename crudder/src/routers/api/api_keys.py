from fastapi import APIRouter, Request, Depends
from fastapi_sso.sso.base import OpenID

import database
from utils.auth import get_logged_user


def get_router():
    router = APIRouter()

    # TODO: create api key
    #
    @router.post("/", include_in_schema=False)
    async def create_api_key_endpoint(
        request: Request,
        user: OpenID = Depends(get_logged_user)
    ):
        api_key = await database.create_api_key(user.provider, user.id)

        return {
            "status": "success",
            "message": "API key created successfully.",
            "api_key": api_key,
        }

    @router.delete("/{api_key_id}", include_in_schema=False)
    async def delete_api_key(request: Request, api_key_id: str):
        # TODO: double check auth
        await database.revoke_api_key(api_key_id)

    return router
