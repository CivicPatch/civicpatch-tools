from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

import services.role_config as role_config_service
import services.role_config_pull_request as role_config_pr
from core.role_config_edits import (
    RoleConfigEditRefused,
    RolesEdit,
    with_role_added,
    with_role_edited,
    with_role_order,
    without_role,
)
from lib.auth import require_route_access
from schemas.common import Identity, RouteCategory, UserRole
from schemas.roles import ReorderRolesRequest, RoleInput
from services.jurisdiction_pull_request import label_for


def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("")
    async def get_roles_endpoint():
        roles = await role_config_service.load_roles()
        return {"data": {"roles": [r.model_dump() for r in roles]}}

    @router.post("", include_in_schema=False)
    async def add_role_endpoint(
        body: RoleInput,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)),
    ):
        return await _proposed(lambda roles: with_role_added(roles, body), f"add {body.label}", user)

    @router.put("/reorder", include_in_schema=False)
    async def reorder_roles_endpoint(
        body: ReorderRolesRequest,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)),
    ):
        return await _proposed(lambda roles: with_role_order(roles, body.role_order), "reorder", user)

    # After /reorder, which would otherwise match as a role id.
    @router.put("/{role_id}", include_in_schema=False)
    async def edit_role_endpoint(
        role_id: str,
        body: RoleInput,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)),
    ):
        return await _proposed(lambda roles: with_role_edited(roles, role_id, body), f"edit {role_id}", user)

    @router.delete("/{role_id}", include_in_schema=False)
    async def remove_role_endpoint(
        role_id: str,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)),
    ):
        """Remove a role from the config file. Once merged, the sync deactivates it: the row
        survives, and membership history with it."""
        return await _proposed(lambda roles: without_role(roles, role_id), f"remove {role_id}", user)

    return router


async def _proposed(edit: RolesEdit, summary: str, user: Identity):
    if user.user_id is None:
        return JSONResponse({"error": "Sign in to change roles."}, status_code=401)
    label = label_for(user.user_id, user.role)
    if label is None:
        return JSONResponse({"error": "Changing roles needs a maintainer."}, status_code=403)
    try:
        opened = await role_config_pr.open_role_config_pull_request(edit, summary, label, user.user_id)
    except RoleConfigEditRefused as error:
        return JSONResponse({"error": str(error)}, status_code=409)
    except role_config_pr.RoleConfigPullRequestAlreadyOpen as error:
        return JSONResponse(
            {"error": "A role change is already waiting to merge.", "pull_request_url": error.url},
            status_code=409,
        )
    except role_config_pr.RoleConfigPullRequestFailed as error:
        return JSONResponse({"error": str(error)}, status_code=502)
    return {"data": opened.model_dump()}
