from uuid import UUID

import database.jurisdictions as jurisdictions_db
import database.users as users_db
import lib.auth_session as auth_session
import lib.cache as cache_service
from fastapi import APIRouter, Depends, HTTPException
from lib.auth import require_route_access
from schemas.common import (
    Identity,
    RouteCategory,
    SetRoleRequest,
    UserRole,
    UserWithRole,
)
from schemas.rollback import RollbackRequest
from services import entry_sheet, rollback


def get_router() -> APIRouter:
    router = APIRouter()

    @router.post("/clear_dashboard_cache", include_in_schema=False)
    async def clear_dashboard_cache_endpoint(
        _: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)
        ),
    ):
        await cache_service.invalidate("dashboard_data")
        return {"status": "ok"}

    @router.get("/users", include_in_schema=False)
    async def list_users_endpoint(
        limit: int = 100,
        offset: int = 0,
        _: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)
        ),
    ):
        rows = await users_db.list_users(limit=limit, offset=offset)
        return {"data": [UserWithRole(**row) for row in rows]}

    @router.put("/users/{user_id}/role", include_in_schema=False)
    async def set_user_role_endpoint(
        user_id: UUID,
        payload: SetRoleRequest,
        identity: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)
        ),
    ):
        user_id_str = str(user_id)
        # Reject self-edits from session/user-key callers. SERVICE_API_KEY carries
        # no user_id, so the comparison can never match — the bootstrap path is exempt.
        if identity.user_id and identity.user_id == user_id_str:
            raise HTTPException(status_code=403, detail="Cannot modify your own role")
        user = await users_db.get_user_by_id(user_id_str)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        await users_db.set_user_role(user_id_str, payload.role.value)
        await auth_session.invalidate_session(
            user["provider"], user["provider_user_id"]
        )
        return {"data": {"id": user_id_str, "role": payload.role.value}}

    @router.get("/users/{user_id}", include_in_schema=False)
    async def get_user_endpoint(
        user_id: UUID,
        _: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)
        ),
    ):
        user = await users_db.get_user_by_id(str(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {"data": UserWithRole(**user)}

    @router.get("/users/{user_id}/rollback-candidates", include_in_schema=False)
    async def list_rollback_candidates_endpoint(
        user_id: UUID,
        _: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)
        ),
    ):
        candidates = await rollback.list_user_assertions(str(user_id))
        return {"data": candidates}

    @router.post("/users/{user_id}/rollback", include_in_schema=False)
    async def rollback_user_endpoint(
        user_id: UUID,
        payload: RollbackRequest,
        identity: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)
        ),
    ):
        if not identity.user_id:
            raise HTTPException(
                status_code=401,
                detail="Rollbacks must be attributable to a signed-in user.",
            )
        # Scoped to this user's own candidates rather than trusting the client's ids
        # outright — the url names whose edits this is meant to undo, and the ids acted
        # on must actually be theirs, not whatever a stray or malicious request sent.
        theirs = {
            candidate.assertion_id
            for candidate in await rollback.list_user_assertions(str(user_id))
        }
        assertion_ids = [aid for aid in payload.assertion_ids if aid in theirs]
        try:
            withdrawn = await rollback.rollback_assertions(
                assertion_ids, identity.user_id, payload.reason
            )
        except rollback.NothingToRollBack:
            raise HTTPException(status_code=409, detail="Nothing to roll back")
        return {"data": {"withdrawn": withdrawn}}

    return router
