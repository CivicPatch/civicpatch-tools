from fastapi import APIRouter, Query

import database.change_logs as database
from schemas.change_logs import ChangeLogBucket, ChangeLogEntry
from schemas.common import Role

# Route access (MAINTAINERS+) is enforced at the mount in main.py.
_BUCKET_ROLES = {
    ChangeLogBucket.QUARANTINE: [Role.DEFAULT.value],
    ChangeLogBucket.ACTIVITY: [Role.CONTRIBUTORS.value, Role.MAINTAINERS.value, Role.ADMINS.value],
}


def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("")
    async def get_change_logs_endpoint(
        bucket: ChangeLogBucket = Query(...),
        page: int = Query(1, ge=1),
        per_page: int = Query(20, ge=1, le=100),
    ):
        offset = (page - 1) * per_page
        total, rows = await database.get_change_logs_for_roles(_BUCKET_ROLES[bucket], per_page, offset)
        total_pages = max(1, (total + per_page - 1) // per_page)
        return {
            "total_items": total,
            "page": page,
            "total_pages": total_pages,
            "data": [ChangeLogEntry(**row) for row in rows],
        }

    return router
