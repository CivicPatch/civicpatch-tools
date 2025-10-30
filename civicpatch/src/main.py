import os
import arel
from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx
# import traceback

# from auth.token_handler import verify_github_action_data_query
from routers.api import router as api_router
from routers.frontend import get_router as get_frontend_router

app = FastAPI()
app.mount("/frontend", StaticFiles(directory="src/frontend"), name="frontend")


civicpatch_webdev_port = os.getenv("CIVICPATCH_WEBDEV_PORT", 8002)
civicpatch_env = os.getenv("CIVICPATCH_ENV", "development")
is_production = civicpatch_env == "production"

templates = Jinja2Templates(directory="src/frontend/templates")
templates.env.globals["is_production"] = is_production

if not is_production:
    hot_reload = arel.HotReload(paths=[arel.Path(".")])
    app.add_websocket_route("/hot-reload", route=hot_reload, name="hot-reload")
    app.add_event_handler("startup", hot_reload.startup)
    app.add_event_handler("shutdown", hot_reload.shutdown)
    templates.env.globals["hot_reload"] = hot_reload

app.include_router(api_router, prefix="/api", tags=["api"])
app.include_router(get_frontend_router(templates), tags=["frontend"])


# Proxy to web-dev-server in development
# @app.get("/dev-modules/{path:path}")
# async def dev_proxy(path: str):
#    """Proxy requests to web-dev-server to avoid CORS"""
#    if is_production:
#        return Response(status_code=404)
#
#    async with httpx.AsyncClient() as client:
#        try:
#            url = f"http://civicpatch-frontend:{civicpatch_webdev_port}/{path}"
#
#            response = await client.get(url)
#            return Response(
#                content=response.content,
#                status_code=response.status_code,
#                media_type=response.headers.get("content-type"),
#            )
#        except httpx.RequestError as err:
#            print("err", err)
#            return Response(status_code=502)


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
#
