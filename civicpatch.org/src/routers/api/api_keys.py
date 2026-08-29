"""A user's own API keys: list, mint, revoke, delete.

Maintainers and above. A key inherits its owner's access, so minting one is handing out that
access in a form that travels — a scraper, a scheduled job, an Apps Script pushing rows.

Every route is scoped to the caller's own keys. Ownership is checked against the key's user, not
just the role, so one maintainer cannot revoke another's.
"""

from fastapi import APIRouter, Depends, HTTPException

import database.users as database
from lib.auth import require_route_access
from schemas.common import Identity, RouteCategory, UserRole


def _maintainer() -> Identity:
    return Depends(
        require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)
    )


def get_router():
    router = APIRouter()

    @router.get("", include_in_schema=False)
    async def list_api_keys_endpoint(user: Identity = _maintainer()):
        """The caller's keys. Only the last four characters — the key itself is shown once, at
        creation, and never stored in a form we could show again."""
        keys = await database.get_api_keys_for_user(
            user.provider, user.provider_user_id
        )
        return {"data": keys}

    @router.post("", include_in_schema=False)
    async def create_api_key_endpoint(user: Identity = _maintainer()):
        """Returns the key once. It is stored hashed, so this response is the only chance to
        copy it."""
        api_key = await database.create_api_key(user.provider, user.provider_user_id)
        return {
            "status": "success",
            "message": "API key created successfully.",
            "api_key": api_key,
        }

    @router.post("/{api_key_id}/revoke", include_in_schema=False)
    async def revoke_api_key_endpoint(
        api_key_id: str, user: Identity = _maintainer()
    ):
        """Revoked rather than deleted: the row stays, so a key that leaked is still on record
        as having existed."""
        await _refuse_unless_owned(api_key_id, user)
        await database.revoke_api_key(api_key_id)
        return {"data": {"revoked": True}}

    @router.delete("/{api_key_id}", include_in_schema=False)
    async def delete_api_key_endpoint(
        api_key_id: str, user: Identity = _maintainer()
    ):
        await _refuse_unless_owned(api_key_id, user)
        await database.delete_api_key(api_key_id)
        return {"data": {"deleted": True}}

    return router


async def _refuse_unless_owned(api_key_id: str, user: Identity) -> None:
    """Being a maintainer grants keys of your own, not power over anybody else's."""
    owner = await database.get_user_by_api_key_id(api_key_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="API key not found")
    if (
        owner["provider"] != user.provider
        or owner["provider_user_id"] != user.provider_user_id
    ):
        raise HTTPException(
            status_code=403, detail="User does not own this resource"
        )
