"""A jurisdiction's governing law: cp.org's own, saved at once, never a pull request."""

import services.governing_law as governing_law_service
from fastapi import APIRouter, Depends, HTTPException
from lib.auth import is_service_key, require_route_access
from schemas.common import Identity, RouteCategory, ServiceKey, UserRole
from shared.schemas import FoundBy, GoverningLaw


def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("/{jurisdiction_ocdid:path}/governing_law", include_in_schema=False)
    async def get_governing_law_endpoint(
        jurisdiction_ocdid: str,
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, service_key=ServiceKey.ACCEPTED)),
    ):
        """Team and the organizations collector's service key: the cache paths it carries are
        not for the public."""
        governing_law = await governing_law_service.get_governing_law(jurisdiction_ocdid)
        return {"data": governing_law.model_dump(mode="json") if governing_law else None}

    @router.put("/{jurisdiction_ocdid:path}/governing_law", include_in_schema=False)
    async def put_governing_law_endpoint(
        jurisdiction_ocdid: str,
        body: GoverningLaw,
        identity: Identity = Depends(
            require_route_access(
                RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS, ServiceKey.ACCEPTED
            )
        ),
    ):
        """The collector's service key or a maintainer; either replaces what was there."""
        if not is_service_key(identity) and identity.user_id is None:
            raise HTTPException(status_code=401, detail="Sign in to set the governing law.")
        # A person's answer is recorded as theirs, whatever the body claims found it.
        governing_law = body if is_service_key(identity) else body.model_copy(update={"found_by": FoundBy.MAINTAINER})
        try:
            await governing_law_service.set_governing_law(jurisdiction_ocdid, governing_law, identity.user_id)
        except governing_law_service.UnknownJurisdiction:
            raise HTTPException(status_code=404, detail=f"No such jurisdiction: {jurisdiction_ocdid}")
        return {"data": governing_law.model_dump(mode="json")}

    return router
