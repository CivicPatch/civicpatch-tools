from typing import Tuple

from database import get_api_usage_for_user

async def can_make_api_request(provider: str, provider_user_id: str) -> Tuple[bool, str]:
    """
    Check if the user can make an API request based on their daily limit.
    """
    usage = await get_api_usage_for_user(provider, provider_user_id)
    if usage["daily_limit"] is None:
        return False, "Daily limit not set, check with admin"
    if usage["usage_count"] >= usage["daily_limit"]:
        return False, f"Daily limit exceeded: {usage['usage_count']} / {usage['daily_limit']}"
    return True, "Allowed"
