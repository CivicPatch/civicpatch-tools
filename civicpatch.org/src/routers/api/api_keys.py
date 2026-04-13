from fastapi import APIRouter, Request, Depends, HTTPException

import database.users as database
from utils.auth_utils import get_user 
from schemas.common import Identity


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
    
    @router.post("/{api_key_id}/revoke", include_in_schema=False)
    async def revoke_api_Key(
        request: Request,
        api_key_id: str,
        user: Identity = Depends(get_user)
    ):
        api_key_owner = await database.get_user_by_api_key_id(api_key_id)
        if api_key_owner is None:
            raise HTTPException(status_code=404, detail="API key not found")

        if api_key_owner["provider"] != user.provider and api_key_owner["provider_user_id"] != user.provider_user_id:
            raise HTTPException(status_code=401, detail="User does not own this resource")

        await database.revoke_api_key(api_key_id)

    @router.delete("/{api_key_id}", include_in_schema=False)
    async def delete_api_key(
        request: Request,
        api_key_id: str,
        user: Identity = Depends(get_user)
    ):
        api_key_owner = await database.get_user_by_api_key_id(api_key_id)
        if api_key_owner is None:
            raise HTTPException(status_code=404, detail="API key not found")

        if api_key_owner["provider"] != user.provider and api_key_owner["provider_user_id"] != user.provider_user_id:
            raise HTTPException(status_code=401, detail="User does not own this resource")

        await database.delete_api_key(api_key_id)

    return router
