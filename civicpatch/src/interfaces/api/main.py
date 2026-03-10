import os

from contextlib import asynccontextmanager
import arel
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from fastapi import Request as FastAPIRequest
from starlette.datastructures import URL
FORWARDED_RESPONSE_HEADERS = {"content-type", "cache-control", "etag", "last-modified", "location"}


# Hack to get url_for to generate https URLs when behind a proxy that terminates SSL
def url_for(request: FastAPIRequest, name: str) -> URL:
    url = request.url_for(name)
    if request.scope.get("scheme") == "https":
        url = url.replace(scheme="https")
    return url

from interfaces.api.routes.backend import get_router as get_backend_router
from interfaces.api.routes.frontend import get_router as get_frontend_router

API_CIVICPATCH_ORG_URL = os.getenv("API_CIVICPATCH_ORG_URL", "http://api_civicpatch_org:8001")

@asynccontextmanager
async def lifespan(app):
    app.state.client = httpx.AsyncClient()
    yield
    await app.state.client.aclose()

app = FastAPI(
    lifespan=lifespan
)
app.mount("/frontend", StaticFiles(directory="src/frontend"), name="frontend")

civicpatch_env = os.getenv("CIVICPATCH_ENV", "development")
is_production = civicpatch_env == "production"

templates = Jinja2Templates(directory="src/frontend/templates")
templates.env.globals["is_production"] = is_production

if not is_production:
    hot_reload = arel.HotReload(paths=[arel.Path("src/frontend")])
    app.add_websocket_route("/hot-reload", route=hot_reload, name="hot-reload")
    app.add_event_handler("startup", hot_reload.startup)
    app.add_event_handler("shutdown", hot_reload.shutdown)
    templates.env.globals["hot_reload"] = hot_reload

app.include_router(get_backend_router(), prefix="/api", tags=["api"])
app.include_router(get_frontend_router(templates), tags=["frontend"])

@app.api_route(
    "/api/api_proxy/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def proxy_to_api_civicpatch_org_endpoint(path: str, request: Request):
    method = request.method
    url = f"{API_CIVICPATCH_ORG_URL}/api/v1/{path}"
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("accept-encoding", None)

    data = await request.body()
    client = request.app.state.client
    resp = await client.request(
        method,
        url,
        headers=headers,
        content=data if method in ["POST", "PUT", "PATCH"] else None,
        params=dict(request.query_params),
    )

    response_headers = {
        k: v for k, v in resp.headers.items()
        if k.lower() in FORWARDED_RESPONSE_HEADERS
    }
    # CRITICAL: Remove headers that prevent double-decompression
    # httpx decompressed the content, so we must remove the encoding header
    response_headers.pop("content-encoding", None)
    response_headers.pop("transfer-encoding", None)

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=response_headers.get("content-type"),
        headers=response_headers,
    )