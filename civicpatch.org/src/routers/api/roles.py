from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

import services.pipeline_issue_resolution as pipeline_issue_resolution_service
import services.role_config as role_config_service
from lib.auth import require_route_access
from schemas.common import Identity, RouteCategory, UserRole
from schemas.roles import ReorderRolesRequest, SetRolesRequest


def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("")
    async def get_roles_endpoint(
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)),
    ):
        roles = await role_config_service.load_roles()
        return {"data": {"roles": [r.model_dump() for r in roles]}}

    @router.put("")
    async def put_roles_endpoint(
        body: SetRolesRequest,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)),
    ):
        """Add or update the submitted roles.

        Upsert only — a role missing from the body is left alone, not removed.
        Removal is DELETE /roles/{role_id}.
        """
        try:
            if body.issue_id:
                await pipeline_issue_resolution_service.resolve_via_config_db(
                    body.roles, user_id=user.user_id, issue_id=body.issue_id
                )
                return {"data": {"ok": True}}
            await role_config_service.set_roles(body.roles, user_id=user.user_id)
        except RuntimeError as e:
            return JSONResponse({"error": str(e)}, status_code=409)
        return {"data": {"ok": True}}

    @router.put("/reorder")
    async def reorder_roles_endpoint(
        body: ReorderRolesRequest,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)),
    ):
        try:
            await role_config_service.reorder_roles(
                body.role_order, body.moved_roles, user_id=user.user_id
            )
        except RuntimeError as e:
            return JSONResponse({"error": str(e)}, status_code=409)
        return {"data": {"ok": True}}

    @router.delete("/{role_id}")
    async def deactivate_role_endpoint(
        role_id: str,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)),
    ):
        """Remove a role. Soft: `status='inactive'`, so the row survives and
        seat history with it. Reads are not filtered — see `get_roles`."""
        deactivated = await role_config_service.deactivate_role(role_id, user_id=user.user_id)
        if not deactivated:
            return JSONResponse({"error": "Role not found"}, status_code=404)
        return {"data": {"ok": True}}

    return router
