from fastapi.responses import JSONResponse
from fastapi import APIRouter, Depends

from database import organizations, posts
from lib.auth import require_route_access
from schemas.common import Identity, RouteCategory, UserRole
from schemas.organizations import CreateOrganizationRequest, UpdateOrganizationRequest


def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("/{jurisdiction_ocdid:path}")
    async def get_organizations_endpoint(jurisdiction_ocdid: str):
        """Every body in a jurisdiction with its posts. Public, like the posts/people/role
        reads — every write below is gated on its own."""
        return {"data": {"organizations": await posts.list_by_organization(jurisdiction_ocdid)}}

    @router.post("/{jurisdiction_ocdid:path}")
    async def create_organization_endpoint(
        jurisdiction_ocdid: str,
        body: CreateOrganizationRequest,
        # Maintainer+, unlike creating a post (`can_create_post`, any signed-in user).
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

    @router.patch("/{organization_id}")
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

    @router.delete("/{organization_id}")
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
