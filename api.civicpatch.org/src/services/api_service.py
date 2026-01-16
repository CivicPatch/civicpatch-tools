from typing import Tuple

import database
from schemas import Identity

async def can_make_api_request(provider: str, provider_user_id: str, request_id: str) -> Tuple[bool, str]:
    """
    Check if the user can make an API request based on their daily limit.
    """
    usage = await database.get_api_usage_for_user(provider, provider_user_id)
    if usage["daily_limit"] is None:
        return False, "Daily limit not set, check with admin"
    if usage["usage_count"] >= usage["daily_limit"]:
        return False, f"Daily limit exceeded: {usage['usage_count']} / {usage['daily_limit']}"
    return True, "Allowed"

async def can_call_request_id(user: Identity, request_id: str) -> bool:
    """
    Check if the user is allowed to call the given request_id.
    """

    if user.roles and "admin" in user.roles:
        return True
    
    owns_request_id = await database.check_user_owns_request_id(
        user.provider, user.provider_user_id, request_id
    )
    return owns_request_id