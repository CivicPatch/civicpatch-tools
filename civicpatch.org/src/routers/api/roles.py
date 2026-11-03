from fastapi import APIRouter, HTTPException

import services.role_config as role_config_service
from shared.schemas import JurisdictionLevel
from shared.utils.id_utils import parse_jurisdiction_ocdid


def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("")
    async def get_roles_endpoint(
        level: JurisdictionLevel | None = None,
        state: str | None = None,
        jurisdiction_ocdid: str | None = None,
    ):
        if jurisdiction_ocdid is None:
            roles = await role_config_service.load_roles(level, state)
        else:
            try:
                parse_jurisdiction_ocdid(jurisdiction_ocdid)
            except ValueError as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
            roles = await role_config_service.load_jurisdiction_roles(jurisdiction_ocdid)
        return {"data": {"roles": [r.model_dump() for r in roles]}}

    return router
