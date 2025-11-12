from fastapi import APIRouter, BackgroundTasks, HTTPException, Security

import services.auth_service as AuthService
from services.github_sync_service import GitDatabaseSync


# TODO: rbac perms needed
def get_router(api_key_header, pool) -> APIRouter:
    router = APIRouter()

    @router.post("/od_sync", include_in_schema=False)
    async def sync_people_endpoint(
        background_tasks: BackgroundTasks,
    ):
        syncer = GitDatabaseSync(pool)
        background_tasks.add_task(syncer.sync)

        return {"status": "running"}

    return router
