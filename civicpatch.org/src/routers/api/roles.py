from fastapi import APIRouter

import services.role_config as role_config_service
from shared.schemas import JurisdictionLevel


def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("")
    async def get_roles_endpoint(level: JurisdictionLevel | None = None, state: str | None = None):
        roles = await role_config_service.load_roles(level, state)
        return {"data": {"roles": [r.model_dump() for r in roles]}}

    return router
