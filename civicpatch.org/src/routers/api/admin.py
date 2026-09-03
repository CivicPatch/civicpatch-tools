from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from supabase import AsyncClient

import database.jurisdictions as jurisdictions_db
import database.users as users_db
import lib.auth_session as auth_session
import lib.cache as cache_service
import lib.supabase_auth as supabase_auth_service
import lib.temporal.client as temporal_client
from services import entry_sheet
from schemas.common import (
    Identity,
    InviteUserRequest,
    PendingInvite,
    UserRole,
    RouteCategory,
    SetRoleRequest,
    UserWithRole,
)
from schemas.open_data import OdSyncRequestSchema
from schemas.sheets import SheetSyncRequestSchema
from lib.auth import require_route_access


def get_router() -> APIRouter:
    router = APIRouter()

    @router.post("/od_sync", include_in_schema=False)
    async def od_sync_endpoint(
        request: OdSyncRequestSchema,
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)),
    ):
        if request.jurisdiction_ocdids:
            await temporal_client.start_targeted_od_sync(request.jurisdiction_ocdids)
        else:
            await temporal_client.trigger_full_od_sync()

        return {"status": "running"}

    def _require_sheet() -> None:
        """503 rather than a cheerful 200 followed by a workflow that dies.

        A manual trigger on an unconfigured deploy should say so at the call, not leave the
        caller reading a traceback in the worker's logs. Missing *credentials* are a different
        failure and surface in Temporal — `SheetsNotConfigured` is non-retryable, so it fails
        fast instead of retrying for days.
        """
        if not entry_sheet.is_configured():
            raise HTTPException(
                status_code=503, detail="ENTRY_SPREADSHEET_ID is not set."
            )

    # Two siblings, so neither the namespace nor one of the kinds is implied. `/sheet_sync`
    # alone would mean "rosters" while its neighbour had to name itself, which is the sort of
    # asymmetry that makes a reader guess.
    @router.post("/sheet_sync/rosters", include_in_schema=False)
    async def sheet_sync_rosters_endpoint(
        request: SheetSyncRequestSchema,
        _: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)
        ),
    ):
        """Re-sync one state's people and posts tabs now, or every state when none is named.

        Both tabs together, never separately: they are one state's data written by one workflow,
        and separate routes would let them drift apart.

        The manual path and the automatic one are the same code — this enqueues the workflow a
        publish enqueues, so a hand-run cannot behave differently from the real thing. Nothing
        here reaches Google in CI, which makes this the only way to exercise the sheet at all.
        """
        _require_sheet()
        # Named state, or every state we hold. Enqueued directly rather than by triggering the
        # sweep schedule: that reads the change log, so triggering it would only re-sync what
        # already changed — which is not what "no state given" is asking for.
        states = (
            [request.state.lower()]
            if request.state
            else [row["code"] for row in await jurisdictions_db.get_states_with_names()]
        )
        for state in states:
            await temporal_client.enqueue_roster_sheet_sync(state)

        return {"status": "running", "states": len(states)}

    @router.post("/sheet_sync/jurisdictions", include_in_schema=False)
    async def sheet_sync_jurisdictions_endpoint(
        _: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)
        ),
    ):
        """Refresh the roster tab's dropdown source — one flat tab covering every state, so it
        takes no argument and has its own trigger (od_sync, not a publish)."""
        _require_sheet()
        await temporal_client.enqueue_jurisdictions_sheet_sync()
        return {"status": "running"}

    @router.post("/clear_dashboard_cache", include_in_schema=False)
    async def clear_dashboard_cache_endpoint(
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)),
    ):
        await cache_service.invalidate("dashboard_data")
        return {"status": "ok"}

    @router.get("/users", include_in_schema=False)
    async def list_users_endpoint(
        limit: int = 100,
        offset: int = 0,
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)),
    ):
        rows = await users_db.list_users(limit=limit, offset=offset)
        return {"data": [UserWithRole(**row) for row in rows]}

    @router.put("/users/{user_id}/role", include_in_schema=False)
    async def set_user_role_endpoint(
        user_id: UUID,
        payload: SetRoleRequest,
        identity: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)),
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
        client: AsyncClient = Depends(supabase_auth_service.get_supabase_admin_client),
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)),
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
        client: AsyncClient = Depends(supabase_auth_service.get_supabase_admin_client),
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)),
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
        client: AsyncClient = Depends(supabase_auth_service.get_supabase_admin_client),
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)),
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
        client: AsyncClient = Depends(supabase_auth_service.get_supabase_admin_client),
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)),
    ):
        try:
            await client.auth.admin.delete_user(str(user_id))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"data": {"revoked": True}}

    return router
