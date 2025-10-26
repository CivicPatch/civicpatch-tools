import hmac
import hashlib
import os
from database import get_server_detail_by_active_api_key
from typing import Any, Tuple

DATABASE_HASH_KEY = os.getenv("DATABASE_HASH_KEY")


def hash_string(string: str, hash_key: str) -> str:
    return hmac.new(hash_key.encode(), string.encode(), hashlib.sha512).hexdigest()


def is_authorized(db_cursor, api_key: str) -> Tuple[Any, str]:
    server_detail = get_server_detail_by_active_api_key(
        db_cursor, DATABASE_HASH_KEY, api_key
    )

    if not server_detail:
        return None, "Invalid or inactive API key"

    if not server_detail["user_email"]:
        return (
            None,
            "No user email associated with the provided API key. Do you have an active API key & user email?",
        )

    if not server_detail["server_url"]:
        return (
            None,
            "No server URL associated with the provided API key. Please set your CivicPatch Server URL in the user details page.",
        )
    return None, ""
