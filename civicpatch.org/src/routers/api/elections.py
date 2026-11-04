from datetime import datetime, timezone

import lib.elections as elections
from fastapi import APIRouter


def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("")
    async def get_elections_endpoint():
        upcoming = await elections.get_upcoming_elections(datetime.now(timezone.utc).date())
        return {"data": upcoming}

    return router
