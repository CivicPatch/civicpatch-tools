from http import HTTPStatus

import httpx
from ..schemas import FetchedPage

# Named, so a host's operator can see who we are and how to reach us.
USER_AGENT = "CivicPatchBot/1.0 (+https://civicpatch.org)"
_REFUSALS = {HTTPStatus.FORBIDDEN, HTTPStatus.TOO_MANY_REQUESTS}


class RefusedByHost(Exception):
    def __init__(self, url: str, status_code: int):
        self.url = url
        self.status_code = status_code
        super().__init__(f"{url} refused with {status_code}")


async def fetch(url: str) -> FetchedPage:
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=30.0) as client:
        response = await client.get(url)
    if response.status_code in _REFUSALS:
        raise RefusedByHost(url, response.status_code)
    response.raise_for_status()
    return FetchedPage(
        url=str(response.url),
        content_type=response.headers.get("content-type", ""),
        body=response.content,
        by_browser=False,
    )
