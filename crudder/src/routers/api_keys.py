import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import database
from utils.auth import get_logged_user

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")


def get_router(templates: Jinja2Templates):
    router = APIRouter()

    @router.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def api_keys_page(request: Request):
        try:
            user = await get_logged_user(request.cookies.get("token"))
            # Fetch user's API keys from database
            provider_user_id = user.id

            api_keys = await database.get_api_keys_for_user("github", provider_user_id)

            return templates.TemplateResponse(
                request=request,
                name="api_keys.html",
                context={"user": user, "api_keys": api_keys},
            )
        except HTTPException:
            return RedirectResponse(url="/", status_code=302)

    return router
