from fastapi.responses import JSONResponse
from fastapi import APIRouter, Depends

from database import organizations, posts
from lib.auth import require_route_access
from schemas.common import Identity, RouteCategory, UserRole
from schemas.organizations import CreateOrganizationRequest, UpdateOrganizationRequest
from schemas.posts import CreatePostRequest


def get_router() -> APIRouter:
    router = APIRouter()

    @router.post("/{organization_id}/posts", include_in_schema=False)
    async def create_post_endpoint(
        organization_id: str,
        body: CreatePostRequest,
        # Any signed-in user, same tier as assigning someone to an existing post
        # (routers/api/memberships.py). Not `can_edit_jurisdiction_data`, which stays
        # maintainer+ and governs editing a post rather than creating one.
        user: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        """Create a post under this organization. 409 if the triple is taken — silently
        returning the existing id would make "created" and "already there" indistinguishable.
        404 if there's no such organization. Registered ahead of the jurisdiction routes below,
        which use a greedy `:path` converter that would otherwise swallow this path too."""
        try:
            post_id = await posts.create(
                organization_id,
                body.role_id,
                body.division_ocdid,
                body.meta_headcount,
                user.user_id,
                body.label,
            )
        except posts.UnknownOrganization:
            return JSONResponse({"error": "No such organization."}, status_code=404)
        if post_id is None:
            return JSONResponse(
                {"error": "A post already exists for that role and division."},
                status_code=409,
            )
        return {"data": {"id": post_id}}

    @router.post("/{organization_id}/default", include_in_schema=False)
    async def set_default_organization_endpoint(
        organization_id: str,
        _: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)
        ),
    ):
        """Make this the body unassigned posts land in, clearing the flag on its siblings.
        Registered ahead of the greedy `:path` routes below, like `/{organization_id}/posts`."""
        if not await organizations.set_default(organization_id):
            return JSONResponse({"error": "No such organization."}, status_code=404)
        return {"data": {"ok": True}}

    @router.get("/{jurisdiction_ocdid:path}")
    async def get_organizations_endpoint(jurisdiction_ocdid: str):
        """Every body in a jurisdiction with its posts. Public, like the posts/people/role
        reads — every write below is gated on its own."""
        return {"data": {"organizations": await posts.list_by_organization(jurisdiction_ocdid)}}

    @router.post("/{jurisdiction_ocdid:path}", include_in_schema=False)
    async def create_organization_endpoint(
        jurisdiction_ocdid: str,
        body: CreateOrganizationRequest,
        # Maintainer+, unlike creating a post, which any signed-in user may do.
        _: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)
        ),
    ):
        """Create a named, non-default organization. 409 if the (jurisdiction, name) pair exists."""
        organization_id = await organizations.create(jurisdiction_ocdid, body.name, body.url)
        if organization_id is None:
            return JSONResponse(
                {"error": "An organization with that name already exists."},
                status_code=409,
            )
        return {"data": {"id": organization_id}}

    @router.patch("/{organization_id}", include_in_schema=False)
    async def update_organization_endpoint(
        organization_id: str,
        body: UpdateOrganizationRequest,
        _: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)
        ),
    ):
        updated = await organizations.update(organization_id, body.name, body.url)
        if not updated:
            return JSONResponse({"error": "No such organization."}, status_code=404)
        return {"data": {"ok": True}}

    @router.delete("/{organization_id}", include_in_schema=False)
    async def delete_organization_endpoint(
        organization_id: str,
        _: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)
        ),
    ):
        """404 covers every refusal: no such organization, the default one, or one with posts."""
        jurisdiction_ocdid = await organizations.delete(organization_id)
        if jurisdiction_ocdid is None:
            return JSONResponse({"error": "Cannot delete that organization."}, status_code=404)
        return {"data": {"ok": True}}

    return router
