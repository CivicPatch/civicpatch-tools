from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
# import traceback

# from auth.token_handler import verify_github_action_data_query
from routers.api import router as api_router
from routers.frontend import router as frontend_router

app = FastAPI()
app.mount("/static", StaticFiles(directory="src/static"), name="static")

app.include_router(api_router, prefix="/api", tags=["api"])
app.include_router(frontend_router, tags=["frontend"])


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
