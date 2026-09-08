import database.change_logs as database
from fastapi import APIRouter, Query
from schemas.change_logs import ChangeLogAuthors, ChangeLogEntry
from schemas.common import UserRole
from schemas.pagination import paginated_response, pagination_offset


def _safe_path(jurisdiction_ocdid: str | None) -> str | None:
    """Folder path for the activity feed's jurisdiction link. Returns None for
    NULL ocdids rather than 500'ing the whole feed. The page's URL is its ocdid, so there is
    nothing left to convert or fail on."""
    return jurisdiction_ocdid or None


def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("")
    async def get_change_logs_endpoint(
        authors: ChangeLogAuthors = Query(ChangeLogAuthors.ALL),
        page: int = Query(1, ge=1),
        per_page: int = Query(20, ge=1, le=100),
    ):
        roles = (
            [UserRole.DEFAULT.value]
            if authors == ChangeLogAuthors.QUARANTINED
            else None
        )
        total, rows = await database.get_change_logs_for_roles(
            roles, per_page, pagination_offset(page, per_page)
        )
        entries = [
            ChangeLogEntry(**row, jurisdiction_path=_safe_path(row["jurisdiction_ocdid"]))
            for row in rows
        ]
        return paginated_response(total, page, per_page, entries)

    return router
