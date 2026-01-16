from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi_sso.sso.base import OpenID

import database
from utils.auth import get_user


# TODO: rbac perms needed
def get_router() -> APIRouter:
    router = APIRouter()

    @router.post("/", include_in_schema=False)
    async def update_user_detail_endpoint(
        request: Request,
        server_url: str = Form(...),
        user: OpenID = Depends(get_user),
    ):
        # Update the user's server_url in the database
        await database.update_user_detail(
            server_url, user.provider, user.provider_user_id
        )

        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
    @router.get("/usage")
    async def get_user_api_usage_endpoint(
        request: Request,
        user: OpenID = Depends(get_user),
    ):
        usage = await database.get_api_usage_for_user(
            user.provider, user.provider_user_id
        )
        return {"api_usage": usage}
    
    return router
