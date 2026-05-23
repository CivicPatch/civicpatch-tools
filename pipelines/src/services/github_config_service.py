import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


def make_github_fetcher(raw_base: str, token: Optional[str] = None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    def fetch(path: str) -> Optional[str]:
        url = f"{raw_base}/{path}"
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
