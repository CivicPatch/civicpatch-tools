import asyncio
import logging
import os
from contextlib import asynccontextmanager
from environment import get_env_vars

from fastapi import (
    Depends,
    FastAPI,
    Request,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import routers.api.admin as api_admin_router
import webhooks.github as github_webhook_router
import routers.api.api_keys as api_keys_router
import routers.api.data as api_data_router
import routers.api.jobs as api_jobs_router
import routers.api.jurisdictions as api_jurisdictions_router
import routers.api.people as api_people_router
import routers.api.pull_requests as api_pull_requests_router
import routers.api.user as api_user_router
import services.github_sync_service
from database.database import (
    close_pool,
    get_api_keys_for_user,
    get_api_usage_for_user,
    get_pool,
    get_user_details,
    user_is_approved,
)
from routers.auth import get_router as auth_router
from schemas.common import Identity, Role, RouteCategory
from services import pubsub_service
from utils.auth_utils import get_optional_user, require_route_access

# Set up logger at the top of your file
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

from fastapi import Request as FastAPIRequest
from starlette.datastructures import URL
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest


# Hack to get url_for to generate https URLs when behind a proxy that terminates SSL
def url_for(request: FastAPIRequest, name: str) -> URL:
    url = request.url_for(name)
    if request.scope.get("scheme") == "https":
        url = url.replace(scheme="https")
    return url


# Ref: https://github.com/tomasvotava/fastapi-sso/blob/master/docs/how-to-guides/use-with-fastapi-security.md

is_production = os.getenv("APP_ENVIRONMENT", "").lower() == "production"

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)


@asynccontextmanager
async def lifespan(app):
    await get_pool()  # open on startup
    await startup_tasks()

    yield

    await close_pool()  # close on shutdown


app = FastAPI(
    title="CivicPatch API",
    description="A starter FastAPI application for CRUD operations.",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="src/frontend/static"), name="static")

templates = Jinja2Templates(directory="src/frontend/templates")

if is_production:
    allowed_origins = [
        "https://civicpatch.org",
        "https://api.civicpatch.org",
        "https://app.civicpatch.org",
        "https://test.civicpatch.org",
        "https://components.civicpatch.org",
    ]
else:
    allowed_origins = [
        "http://localhost:8000",
        "http://localhost:8001",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home(request: Request, user: Identity = Depends(get_optional_user)):
    env = get_env_vars()
    try:
        provider_user_id = user.provider_user_id
        api_keys = await get_api_keys_for_user(user.provider, provider_user_id)
        api_usage = await get_api_usage_for_user(user.provider, provider_user_id)
        approved_user = await user_is_approved(user.provider, provider_user_id)
        user_details = await get_user_details(user.provider, provider_user_id)
    except Exception as e:
        user = None
        api_keys = []
        api_usage = {}
        approved_user = False
        user_details = None

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "user": user,
            "api_keys": api_keys,
            "api_usage": api_usage,
            "approved_user": approved_user,
            "maintainer_email": env.get("MAINTAINER_EMAIL"),
            "user_details": user_details,
        },
    )


app.include_router(
    api_admin_router.get_router(),
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[
        Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.ADMINS]))
    ],
)
app.include_router(
    api_jurisdictions_router.get_router(),
    prefix="/api/v1/jurisdictions",
    tags=["jurisdictions"],
    dependencies=[
        Depends(require_route_access(RouteCategory.PUBLIC))
    ],  # public route for now
)

app.include_router(
    api_people_router.get_router(),
    prefix="/api/v1/people",
    tags=["people"],
    dependencies=[Depends(require_route_access(RouteCategory.PUBLIC))],
)

app.include_router(
    api_jobs_router.get_router(api_key_header),
    prefix="/api/v1/jobs",
    tags=["jobs"],
    dependencies=[
        Depends(require_route_access(RouteCategory.TEAM_REQUIRED, ["default"]))
    ],
)

app.include_router(
    api_pull_requests_router.get_router(api_key_header),
    prefix="/api/v1/pull_requests",
    tags=["pull_requests"],
    # Dependencies set within router
)

# Allow you to create your api keys
# Mostly for civicpatch users who need to contribute data
app.include_router(
    api_keys_router.get_router(),
    prefix="/api/internal/api_keys",
    tags=["api_keys"],
    dependencies=[
        Depends(require_route_access(RouteCategory.TEAM_REQUIRED, ["default"]))
    ],
)

app.include_router(
    api_data_router.get_router(),
    prefix="/api/v1/data",
    tags=["data"],
    dependencies=[Depends(require_route_access(RouteCategory.PUBLIC))],
)

app.include_router(
    api_user_router.get_router(),
    prefix="/api/internal/user",
    tags=["user"],
    dependencies=[Depends(require_route_access(RouteCategory.AUTHENTICATED))],
)

app.include_router(
    auth_router(is_production),
    prefix="/api/v1/auth",
    tags=["auth"],
    dependencies=[Depends(require_route_access(RouteCategory.PUBLIC))],
)

app.include_router(
    github_webhook_router.get_router(),
    prefix="/webhooks/github",
    tags=["webhooks"],
)


@app.get("/api/v1/me", tags=["auth"])
async def get_me(user: Identity = Depends(get_optional_user)):
    """
    Returns the authenticated user's identity info.
    """
    if not user:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "provider": user.provider,
        "provider_user_id": user.provider_user_id,
        "email": user.email,
        "teams": getattr(user, "teams", None),
    }


@app.get("/api/v1/sse/jobs/status", include_in_schema=False)
async def sse_job_status(job_type: str, jurisdiction_ocdid: str, request: Request):
    key = f"{job_type}:{jurisdiction_ocdid}"

    async def event_generator():
        try:
            async for message in pubsub_service.subscribe(key):
                if await request.is_disconnected():
                    break
                yield f"data: {message}\n\n"
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _hourly_pr_sync():
    while True:
        await asyncio.sleep(3600)
        await services.github_sync_service.sync_open_pr_state()


async def startup_tasks():
    print("Running startup tasks...")
    asyncio.create_task(services.github_sync_service.bulk_sync())
    asyncio.create_task(services.github_sync_service.sync_open_pr_state())
    asyncio.create_task(_hourly_pr_sync())
