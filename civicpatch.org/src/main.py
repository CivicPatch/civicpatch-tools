import asyncio
import logging
import os
from contextlib import asynccontextmanager

import lib.pubsub as pubsub_service
import routers.api.admin as api_admin_router
import routers.api.api_keys as api_keys_router
import routers.api.change_logs as api_change_logs_router
import routers.api.coverage as api_coverage_router
import routers.api.data as api_data_router
import routers.api.jurisdictions as api_jurisdictions_router
import routers.api.leaderboard as api_leaderboard_router
import routers.api.assertions as api_assertions_router
import routers.api.memberships as api_memberships_router
import routers.api.people as api_people_router
import routers.api.imports as api_imports_router
import routers.api.posts as api_posts_router
import routers.api.pipeline_runs as api_pipeline_runs_router
import routers.api.review_actions as api_review_actions_router
import routers.api.review_cards as api_review_cards_router
import routers.api.requests as api_requests_router
import routers.api.review_sessions as api_review_sessions_router
import routers.api.roles as api_roles_router
import routers.api.summary as api_summary_router
import routers.api.user as api_user_router
import routers.webhooks.blog_sync as blog_sync_webhook_router
import routers.webhooks.github as github_webhook_router
from database.database import (
    close_pool,
    get_pool,
)
from fastapi import (
    Depends,
    FastAPI,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from frontend.vite import vite_asset, vite_css
from lib.auth import get_optional_user, get_ws_user, require_route_access
from lib.middleware import require_display_name
from lib.supabase_auth import create_supabase_admin_client, create_supabase_client
from routers.frontend import get_router as frontend_router
from routers.sso import get_router as auth_router
from schemas.common import Identity, UserRole, RouteCategory
from schemas.ws import SubscribeMessage

# Set up logger at the top of your file
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

from fastapi import Request as FastAPIRequest
from starlette.datastructures import URL


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
    await get_pool()
    app.state.supabase = await create_supabase_client()
    # Held separately from app.state.supabase to keep auth.admin.* calls isolated
    # from user sign-in flows. See supabase-py issue #1143.
    app.state.supabase_admin = await create_supabase_admin_client()
    yield
    for client in (app.state.supabase, app.state.supabase_admin):
        try:
            await client.auth.close()
        except Exception:
            pass
    await close_pool()


app = FastAPI(
    title="CivicPatch API",
    description="A starter FastAPI application for CRUD operations.",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/frontend", StaticFiles(directory="src/frontend"), name="frontend")

templates = Jinja2Templates(directory="src/frontend/templates")

templates.env.globals["vite_asset"] = lambda path: vite_asset(path, is_production)
templates.env.globals["vite_css"] = lambda path: vite_css(path, is_production)
templates.env.globals["is_production"] = is_production

if is_production:
    allowed_origins = [
        "https://civicpatch.org",
        "https://staging.civicpatch.org",
    ]
else:
    allowed_origins = [
        "http://localhost:8000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_headers=["*"],
)

app.middleware("http")(require_display_name)


app.include_router(
    api_admin_router.get_router(),
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[
        Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS))
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
    api_pipeline_runs_router.get_router(api_key_header),
    prefix="/api/v1/pipeline_runs",
    tags=["pipeline_runs"],
    dependencies=[
        Depends(require_route_access(RouteCategory.AUTHENTICATED))
    ],
)

# Two routers, one prefix: reading a card and acting on one are the same surface to the
# frontend, and are separate files because a read that can only 404 and a write that publishes
# to open-data fail in very different ways.
app.include_router(
    api_review_cards_router.get_router(api_key_header),
    prefix="/api/v1/reviews",
    tags=["review"],
    # Dependencies set within router
)

app.include_router(
    api_review_actions_router.get_router(api_key_header),
    prefix="/api/v1/reviews",
    tags=["review"],
    # Dependencies set within router
)

# Seating a person. Always a transition — landing on a different post closes the old
# membership and opens a new one, so membership history survives.
app.include_router(
    api_assertions_router.get_router(),
    prefix="/api/v1/assertions",
    tags=["assertions"],
)

app.include_router(
    api_memberships_router.get_router(),
    prefix="/api/v1/memberships",
    tags=["memberships"],
)

# Every body in a jurisdiction with its posts.
app.include_router(
    api_posts_router.get_router(),
    prefix="/api/v1/posts",
    tags=["posts"],
)

# Curated-sheet imports: start one, watch it, release a stuck lock.
app.include_router(
    api_imports_router.get_router(),
    prefix="/api/internal/imports",
    tags=["imports"],
)

# Allow you to create your api keys
# Mostly for civicpatch users who need to contribute data
app.include_router(
    api_keys_router.get_router(),
    prefix="/api/internal/api_keys",
    tags=["api_keys"],
    dependencies=[
        Depends(require_route_access(RouteCategory.AUTHENTICATED))
    ],
)

app.include_router(
    api_data_router.get_router(),
    prefix="/api/v1/data",
    tags=["data"],
    dependencies=[Depends(require_route_access(RouteCategory.PUBLIC))],
)

app.include_router(
    api_roles_router.get_router(),
    prefix="/api/v1/roles",
    tags=["roles"],
    # Dependencies set within router
)

app.include_router(
    api_change_logs_router.get_router(),
    prefix="/api/v1/change_logs",
    tags=["change_logs"],
    dependencies=[Depends(require_route_access(RouteCategory.AUTHENTICATED))],
)

app.include_router(
    api_requests_router.get_router(api_key_header),
    prefix="/api/v1/requests",
    tags=["requests"],
)

app.include_router(
    api_leaderboard_router.get_router(),
    prefix="/api/v1/leaderboard",
    tags=["leaderboard"],
    dependencies=[Depends(require_route_access(RouteCategory.PUBLIC))],
)

app.include_router(
    api_summary_router.get_router(),
    prefix="/api/v1/summary",
    tags=["summary"],
)

app.include_router(
    api_coverage_router.get_router(),
    prefix="/api/v1/coverage",
    tags=["coverage"],
    dependencies=[Depends(require_route_access(RouteCategory.PUBLIC))],
)

app.include_router(
    api_review_sessions_router.get_router(),
    prefix="/api/v1/review-sessions",
    tags=["review-sessions"],
    dependencies=[
        Depends(require_route_access(RouteCategory.AUTHENTICATED))
    ],
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

app.include_router(
    blog_sync_webhook_router.get_router(),
    prefix="/webhooks/blog-sync",
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
        "display_name": user.display_name,
        "avatar_url": None,
    }


@app.get("/api/v1/sse/pipeline_runs/status", include_in_schema=False)
async def sse_pipeline_run_status(jurisdiction_ocdid: str, request: Request):
    key = f"pipeline_run_status:{jurisdiction_ocdid}"

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


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    user = await get_ws_user(websocket)
    if not user:
        await websocket.close(code=1008)
        return

    subscribed: set[str] = set()
    tasks: dict[str, asyncio.Task] = {}

    async def stream_topic(topic: str):
        async for message in pubsub_service.subscribe(topic):
            if message.startswith(":"):  # skip SSE heartbeat artifacts
                continue
            await websocket.send_text(message)

    try:
        while True:
            raw = await websocket.receive_text()
            msg = SubscribeMessage.model_validate_json(raw)
            if msg.action == "subscribe":
                for topic in msg.topics:
                    if topic not in subscribed:
                        subscribed.add(topic)
                        tasks[topic] = asyncio.create_task(stream_topic(topic))
            elif msg.action == "unsubscribe":
                for topic in msg.topics:
                    if topic in tasks:
                        tasks.pop(topic).cancel()
                        subscribed.discard(topic)
    except WebSocketDisconnect:
        for task in tasks.values():
            task.cancel()


# Must be last: contains a /{path:path} catch-all for jurisdiction pages
app.include_router(frontend_router(templates))
