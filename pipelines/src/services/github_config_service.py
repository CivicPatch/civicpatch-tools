import logging
from typing import Optional

import httpx

OPEN_DATA_RAW_BASE = "https://raw.githubusercontent.com/CivicPatch/open-data/refs/heads/main"

logger = logging.getLogger(__name__)


def make_github_fetcher(token: Optional[str] = None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    def fetch(path: str) -> Optional[str]:
        url = f"{OPEN_DATA_RAW_BASE}/{path}"
        try:
            with httpx.Client(headers=headers, timeout=10) as client:
                response = client.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.warning("github_config_service: could not fetch %s: %s", path, e)
            return None

    return fetch
