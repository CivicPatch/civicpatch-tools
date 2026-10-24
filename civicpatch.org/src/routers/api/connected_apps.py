"""The OAuth apps (e.g. ChatGPT) a maintainer approved on the consent page: list, disconnect.

Maintainers and above, like their API keys; each route acts only on the caller's own approvals.
"""

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

import environment
import services.connected_apps as service
from lib.auth import require_route_access
from lib.supabase_oauth import SupabaseAuthError
from schemas.common import Identity, RouteCategory, UserRole

SUPABASE_FAILED = "Supabase could not be reached for your connected apps."


def _maintainer() -> Identity:
    return Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS))


def get_router():
    router = APIRouter()

    @router.get("", include_in_schema=False)
    async def list_connected_apps_endpoint(user: Identity = _maintainer()):
        url, key = environment.supabase_url_and_secret_key()
        try:
            apps = await service.fetch_connected_apps(url, key, user.provider_user_id)
        except SupabaseAuthError as error:
            raise HTTPException(status_code=HTTPStatus.BAD_GATEWAY, detail=SUPABASE_FAILED) from error
        return {"data": [app.model_dump() for app in apps]}

    @router.delete("/{client_id}", include_in_schema=False)
    async def disconnect_app_endpoint(client_id: UUID, user: Identity = _maintainer()):
        url, key = environment.supabase_url_and_secret_key()
        try:
            await service.disconnect_app(url, key, user.provider_user_id, str(client_id))
        except SupabaseAuthError as error:
            if error.status == HTTPStatus.NOT_FOUND:
                raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="No such connected app.") from error
            raise HTTPException(status_code=HTTPStatus.BAD_GATEWAY, detail=SUPABASE_FAILED) from error
        return {"data": {"disconnected": True}}

    return router
