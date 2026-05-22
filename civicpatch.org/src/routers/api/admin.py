from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, model_validator
from supabase import AsyncClient

import database.users as users_db
import lib.auth_session as auth_session
import lib.cache as cache_service
import lib.supabase_auth as supabase_auth_service
import core.open_data_sync as data_sync
import core.pull_request_sync as pr_sync
import lib.temporal.map_client as map_client
from schemas.common import (
    Identity,
    InviteUserRequest,
    PendingInvite,
    Role,
    RouteCategory,
    SetRoleRequest,
    UserWithRole,
)
from schemas.open_data import OdSyncRequestSchema
from lib.auth import require_route_access
from shared.utils.config_utils import get_states


def _valid_state_codes() -> set[str]:
    return {s["code"] for s in get_states()}


class MapSyncRequest(BaseModel):
    state: Optional[str] = None

    @model_validator(mode="after")
    def validate_state(self) -> "MapSyncRequest":
        if self.state is not None and self.state not in _valid_state_codes():
            raise ValueError(f"state must be one of: {sorted(_valid_state_codes())}")
        return self

def get_router() -> APIRouter:
    router = APIRouter()

    @router.post("/od_sync", include_in_schema=False)
    async def od_sync_endpoint(
        request: OdSyncRequestSchema,
        background_tasks: BackgroundTasks,
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.ADMINS)),
    ):
        background_tasks.add_task(data_sync.sync, request)

        return {"status": "running"}

    @router.post("/pr_sync", include_in_schema=False)
    async def pr_sync_endpoint(
        background_tasks: BackgroundTasks,
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.ADMINS)),
    ):
        background_tasks.add_task(pr_sync.sync_open_pr_state)
        return {"status": "running"}

    @router.post("/clear_dashboard_cache", include_in_schema=False)
    async def clear_dashboard_cache_endpoint(
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.ADMINS)),
    ):
        await cache_service.invalidate("dashboard_data")
        return {"status": "ok"}

    @router.post("/map_sync", include_in_schema=False)
    async def map_sync_endpoint(
        request: MapSyncRequest = MapSyncRequest(),
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.ADMINS)),
    ):
        try:
            workflow_id = await map_client.start_sync_jurisdiction_map_workflow(request.state)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        return {"workflow_id": workflow_id, "state": request.state}

    @router.get("/users", include_in_schema=False)
    async def list_users_endpoint(
        limit: int = 100,
        offset: int = 0,
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.ADMINS)),
    ):
        rows = await users_db.list_users(limit=limit, offset=offset)
        return {"data": [UserWithRole(**row) for row in rows]}

    @router.put("/users/{user_id}/role", include_in_schema=False)
    async def set_user_role_endpoint(
        user_id: UUID,
        payload: SetRoleRequest,
        identity: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.ADMINS)),
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
        await auth_session.invalidate_session(user["provider"], user["provider_user_id"])
        return {"data": {"id": user_id_str, "role": payload.role.value}}

    @router.post("/users/invite", include_in_schema=False)
    async def invite_user_endpoint(
        payload: InviteUserRequest,
        client: AsyncClient = Depends(supabase_auth_service.get_supabase_client),
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.ADMINS)),
    ):
        try:
            await client.auth.admin.invite_user_by_email(payload.email)
        except Exception as exc:
            message = str(exc)
            if "already" in message.lower():
                raise HTTPException(status_code=409, detail="User already exists")
            raise HTTPException(status_code=400, detail=message)
        return {"data": {"sent": True}}

    @router.get("/users/pending", include_in_schema=False)
    async def list_pending_invites_endpoint(
        client: AsyncClient = Depends(supabase_auth_service.get_supabase_client),
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.ADMINS)),
    ):
        # per_page=100 fits our scale (small team); revisit if total users grows past that.
        try:
            users = await client.auth.admin.list_users(per_page=100)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

        pending = [
            PendingInvite(
                id=str(user.id),
                email=getattr(user, "email", None),
                invited_at=user.invited_at.isoformat() if user.invited_at else None,
            )
            for user in users
            if user.invited_at and not user.last_sign_in_at
        ]
        return {"data": pending}

    @router.post("/users/{user_id}/resend-invite", include_in_schema=False)
    async def resend_invite_endpoint(
        user_id: UUID,
        client: AsyncClient = Depends(supabase_auth_service.get_supabase_client),
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.ADMINS)),
    ):
        try:
            user_response = await client.auth.admin.get_user_by_id(str(user_id))
        except Exception:
            raise HTTPException(status_code=404, detail="User not found")
        user_obj = getattr(user_response, "user", user_response)
        email = getattr(user_obj, "email", None)
        if not email:
            raise HTTPException(status_code=404, detail="User has no email on file")
        try:
            await client.auth.admin.invite_user_by_email(email)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"data": {"sent": True}}

    @router.delete("/users/{user_id}/invite", include_in_schema=False)
    async def revoke_invite_endpoint(
        user_id: UUID,
        client: AsyncClient = Depends(supabase_auth_service.get_supabase_client),
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.ADMINS)),
    ):
        try:
            await client.auth.admin.delete_user(str(user_id))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"data": {"revoked": True}}

    return router
