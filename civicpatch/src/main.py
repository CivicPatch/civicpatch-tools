import os

import arel
import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# import traceback
# from auth.token_handler import verify_github_action_data_query
from routers.api import router as api_router
from routers.frontend import get_router as get_frontend_router

CRUDDER_URL = os.getenv("CRUDDER_URL", "http://localhost:8001")
CRUDDER_SHARED_TOKEN = os.getenv("CRUDDER_SHARED_TOKEN")

app = FastAPI()
app.mount("/frontend", StaticFiles(directory="src/frontend"), name="frontend")


# civicpatch_webdev_port = os.getenv("CIVICPATCH_WEBDEV_PORT", 8002)
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

app.include_router(api_router, prefix="/api", tags=["api"])
app.include_router(get_frontend_router(templates), tags=["frontend"])


@app.api_route(
    "/api/crudder/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def proxy_to_crudder(path: str, request: Request):
    # Inject Authorization header from env var
    if not CRUDDER_SHARED_TOKEN:
        raise HTTPException(status_code=500, detail="Missing CRUDDER_SHARED_TOKEN")

    method = request.method
    url = f"{CRUDDER_URL}/api/{path}"
    headers = dict(request.headers)
    headers.pop("host", None)
    headers["Authorization"] = f"{CRUDDER_SHARED_TOKEN}"  # Inject token

    data = await request.body()
    async with httpx.AsyncClient() as client:
        resp = await client.request(
            method,
            url,
            headers=headers,
            content=data if method in ["POST", "PUT", "PATCH"] else None,
            params=dict(request.query_params),
        )
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type"),
    )


# @app.exception_handler(Exception)
# async def exception_handler(request: Request, exc: Exception):
#    stack_trace = traceback.format_exc()
#    return JSONResponse(
#        status_code=500,
#        content={
#            "detail": str(exc),
#            "stack_trace": stack_trace
#        },
#    )
