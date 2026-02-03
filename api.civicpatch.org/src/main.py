import os
from contextlib import asynccontextmanager

from fastapi import (
    FastAPI,
    Request,
    Depends,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from schemas import Identity, RouteCategory
import asyncio

import routers.api.admin as api_admin_router
import routers.api.api_keys as api_keys_router
import routers.api.jurisdictions as api_jurisdictions_router
import routers.api.people as api_people_router
import routers.api.pipelines as api_pipelines_router
import routers.api.jobs as api_jobs_router
import routers.api.user as api_user_router
from routers.auth import get_router as auth_router
from database import (
    get_api_keys_for_user,
    get_api_usage_for_user,
    get_user_details,
    pool,
    user_is_approved,
)
from utils.auth import require_route_access, get_optional_user, require_route_access_optional
from services.memory_pub_sub_service import memory_pubsub
from fastapi.responses import StreamingResponse

# Only purpose is to manage users, their API keys, and move data from 3rd party servers
# to GitHub Actions.
# Update 2025/10/24
# Goal has expanded to -- whatever the civicpatch servers need to sync data
# to and from the open-data repo
# Ref: https://github.com/tomasvotava/fastapi-sso/blob/master/docs/how-to-guides/use-with-fastapi-security.md

INSTANCE_URL = os.getenv("INSTANCE_URL", "http://127.0.0.1:8001")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_CALLBACK_URL = f"{INSTANCE_URL}/auth/github/callback"
CRUDDER_DB_URL = os.getenv("CRUDDER_DB_URL")

MAINTAINER_EMAIL = os.getenv("MAINTAINER_EMAIL")
APP_ENVIRONMENT = os.getenv("APP_ENVIRONMENT")
GITHUB_WORKFLOW_TOKEN = os.getenv("GITHUB_WORKFLOW_TOKEN")
DATABASE_HASH_KEY = os.getenv("DATABASE_HASH_KEY")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

STORAGE_ENDPOINT = os.getenv("STORAGE_ENDPOINT")
STORAGE_ACCESS_KEY_ID = os.getenv("STORAGE_ACCESS_KEY_ID")
STORAGE_SECRET_ACCESS_KEY = os.getenv("STORAGE_SECRET_ACCESS_KEY")

# db_connection = sqlite3.connect("data/database.db")
# db_cursor = db_connection.cursor()

if not all(
    [
        MAINTAINER_EMAIL,
        GITHUB_CLIENT_ID,
        GITHUB_CLIENT_SECRET,
        CRUDDER_DB_URL,
        APP_ENVIRONMENT,
        GITHUB_WORKFLOW_TOKEN,
        DATABASE_HASH_KEY,
        JWT_SECRET_KEY,
        STORAGE_ENDPOINT,
        STORAGE_ACCESS_KEY_ID,
        STORAGE_SECRET_ACCESS_KEY,
    ]
):
    missing_vars = [
        var
        for var, val in {
            "MAINTAINER_EMAIL": MAINTAINER_EMAIL,
            "GITHUB_CLIENT_ID": GITHUB_CLIENT_ID,
            "GITHUB_CLIENT_SECRET": GITHUB_CLIENT_SECRET,
            "CRUDDER_DB_URL": CRUDDER_DB_URL,
            "APP_ENVIRONMENT": APP_ENVIRONMENT,
            "GITHUB_WORKFLOW_TOKEN": GITHUB_WORKFLOW_TOKEN,
            "DATABASE_HASH_KEY": DATABASE_HASH_KEY,
            "JWT_SECRET_KEY": JWT_SECRET_KEY,
            "STORAGE_ENDPOINT": STORAGE_ENDPOINT,
            "STORAGE_ACCESS_KEY_ID": STORAGE_ACCESS_KEY_ID,
            "STORAGE_SECRET_ACCESS_KEY": STORAGE_SECRET_ACCESS_KEY,
        }.items()
        if not val
    ]
    print(f"Missing environment variables: {', '.join(missing_vars)}")
    raise ValueError("One or more required environment variables are not set.")

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)

is_production = APP_ENVIRONMENT.lower() == "production"


@asynccontextmanager
async def lifespan(instance: FastAPI):
    await pool.open()
    yield
    await pool.close()


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
        "https://api.civicpatch.org"
        "https://app.civicpatch.org"
        "https://components.civicpatch.org",
    ]
else:
    allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_origins=allowed_origins,
)

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home(
    request: Request,
    user: Identity = Depends(get_optional_user)
):
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
            "maintainer_email": MAINTAINER_EMAIL,
            "user_details": user_details,
        },
    )

app.include_router(
    api_admin_router.get_router(api_key_header, pool),
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_route_access(RouteCategory.ADMIN_ONLY))],
)
app.include_router(
    api_jurisdictions_router.get_router(),
    prefix="/api/v1/jurisdictions",
    tags=["jurisdictions"],
    dependencies=[Depends(require_route_access_optional(RouteCategory.COMPONENT_API))]
)

app.include_router(
    api_people_router.get_router(),
    prefix="/api/v1/people",
    tags=["people"],
    dependencies=[Depends(require_route_access_optional(RouteCategory.COMPONENT_API))]
)

app.include_router(
    api_pipelines_router.get_router(api_key_header),
    prefix="/api/internal/pipelines",
    tags=["pipelines"],
    dependencies=[Depends(require_route_access(RouteCategory.INTERNAL_API))]
)

app.include_router(
    api_jobs_router.get_router(api_key_header),
    prefix="/api/v1/jobs",
    tags=["jobs"],
    dependencies=[Depends(require_route_access(RouteCategory.JOBS_API))]
)

# Allow you to create your api keys
# Mostly for civicpatch users who need to contribute data
app.include_router(
    api_keys_router.get_router(), 
    prefix="/api/internal/api_keys", 
    tags=["api_keys"],
    dependencies=[Depends(require_route_access(RouteCategory.INTERNAL_API))]
)

app.include_router(
    api_user_router.get_router(), 
    prefix="/api/internal/user", 
    tags=["user"],
    dependencies=[Depends(require_route_access(RouteCategory.INTERNAL_API))]
)

app.include_router(
    auth_router(is_production),
    prefix="/auth",
    tags=["auth"],
)

@app.get("/api/v1/sse/jobs/status", include_in_schema=False)
async def sse_job_status(job_type: str, jurisdiction_ocdid: str, request: Request):
    key = f"{job_type}:{jurisdiction_ocdid}"
    queue = memory_pubsub.subscribe(key)
    print("grabbing sse for key:", key)

    async def event_generator():
        try:
            while True:
                try:
                # Wait for data with a timeout, send heartbeat if nothing comes
                    data = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    # On timeout, unsubscribe and exit if client disconnected
                    if await request.is_disconnected():
                        print("Client disconnected, stopping SSE")
                        break

        except asyncio.CancelledError:
            pass
        finally:
            memory_pubsub.unsubscribe(key, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )