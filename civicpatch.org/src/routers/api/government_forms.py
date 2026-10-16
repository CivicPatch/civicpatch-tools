"""A jurisdiction's government form: cp.org's own, saved at once, never a pull request."""

import services.government_form as government_form_service
from fastapi import APIRouter, Depends, HTTPException
from lib.auth import is_service_key, require_route_access
from pydantic import BaseModel
from schemas.common import Identity, RouteCategory, ServiceKey, UserRole
from shared.schemas import GovernmentForm


class GovernmentFormRequest(BaseModel):
    government_form: GovernmentForm


def get_router() -> APIRouter:
    router = APIRouter()

    @router.put("/{jurisdiction_ocdid:path}/government_form", include_in_schema=False)
    async def put_government_form_endpoint(
        jurisdiction_ocdid: str,
        body: GovernmentFormRequest,
        identity: Identity = Depends(
            require_route_access(
                RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS, ServiceKey.ACCEPTED
            )
        ),
    ):
        """A maintainer sets it; the pipeline's service key fills it, only while none is set."""
        try:
            if is_service_key(identity):
                await government_form_service.fill_government_form(jurisdiction_ocdid, body.government_form)
            elif identity.user_id is None:
                raise HTTPException(status_code=401, detail="Sign in to set the government form.")
            else:
                await government_form_service.set_government_form(
                    jurisdiction_ocdid, body.government_form, identity.user_id
                )
        except government_form_service.UnknownJurisdiction:
            raise HTTPException(status_code=404, detail=f"No such jurisdiction: {jurisdiction_ocdid}")
        except government_form_service.GovernmentFormNotAtLevel as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except government_form_service.GovernmentFormAlreadySet:
            raise HTTPException(status_code=409, detail="A government form is already set.")
        details = await government_form_service.jurisdiction_details_fields(jurisdiction_ocdid)
        return {"data": details.model_dump()}

    return router
