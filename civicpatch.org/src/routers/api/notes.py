from fastapi import APIRouter, Depends, HTTPException, Query

import database.notes as database
from schemas.common import CreateNoteRequest, Identity, NoteResponse, Role, RouteCategory
from utils.auth_utils import require_route_access


def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("")
    async def get_notes_endpoint(
        jurisdiction_ocdid: str = Query(...),
        page: int = Query(1, ge=1),
        per_page: int = Query(20, ge=1, le=100),
        _user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.DEFAULT])),
    ):
        offset = (page - 1) * per_page
        total, notes = await database.get_notes_for_jurisdiction(jurisdiction_ocdid, per_page, offset)
        total_pages = max(1, (total + per_page - 1) // per_page)
        return {
            "total_items": total,
            "page": page,
            "total_pages": total_pages,
            "data": [NoteResponse(**n) for n in notes],
        }

    @router.post("")
    async def create_note_endpoint(
        body: CreateNoteRequest,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.CONTRIBUTORS])),
    ):
        if not user.user_id:
            raise HTTPException(status_code=401, detail="User ID not available")
        note = await database.create_note(body.jurisdiction_ocdid, body.body, user.user_id)
        return {"data": NoteResponse(**note)}

    return router
