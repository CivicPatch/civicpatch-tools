import os
from database.users import get_server_detail_by_active_api_key
from typing import Any, Optional, Tuple
from schemas.requests import ServerDetail


async def is_authorized(api_key: str) -> Tuple[Optional[ServerDetail], str]:
    server_detail = await get_server_detail_by_active_api_key(api_key)

    if not server_detail:
        return None, "Invalid or inactive API key"

    return server_detail, ""
