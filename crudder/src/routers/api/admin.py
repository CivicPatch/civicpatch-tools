from fastapi import APIRouter, BackgroundTasks, HTTPException, Security

import services.auth as AuthService
from services.github_sync_service import GitDatabaseSync


# TODO: rbac perms needed
def get_router(api_key_header, pool) -> APIRouter:
    router = APIRouter()

    @router.post("/od_sync", include_in_schema=False)
    async def sync_people_endpoint(
        background_tasks: BackgroundTasks,
        authorization: str = Security(api_key_header),
    ):
        if not authorization and not authorization.strip():
            raise HTTPException(status_code=401, detail="Missing Authorization header")

        _server_detail, error_string = await AuthService.is_authorized(authorization)
        if error_string:
            raise HTTPException(status_code=403, detail=error_string)

        syncer = GitDatabaseSync(pool)
        background_tasks.add_task(syncer.sync)

        return {"status": "running"}

    return router
