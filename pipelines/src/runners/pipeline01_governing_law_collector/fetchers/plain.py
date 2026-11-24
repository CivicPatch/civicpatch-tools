from http import HTTPStatus

import httpx
import services.polite as polite
from ..schemas import FetchedPage

REFUSALS = {HTTPStatus.FORBIDDEN, HTTPStatus.TOO_MANY_REQUESTS}
CHALLENGE_HEADER = "cf-mitigated"
CHALLENGE_VALUE = "challenge"


class RefusedByHost(Exception):
    def __init__(self, url: str, status_code: int, *, challenged: bool = False):
        self.url = url
        self.status_code = status_code
        self.challenged = challenged
        super().__init__(f"{url} refused with {status_code}")


async def _obey_request(request: httpx.Request) -> None:
    await polite.obey_host(str(request.url))


async def fetch(url: str) -> FetchedPage:
    async with httpx.AsyncClient(
        headers={"User-Agent": polite.USER_AGENT}, follow_redirects=True, timeout=30.0, event_hooks={"request": [_obey_request]}
    ) as client:
        response = await client.get(url)
    if response.status_code in REFUSALS:
        raise RefusedByHost(str(response.url), response.status_code, challenged=response.headers.get(CHALLENGE_HEADER) == CHALLENGE_VALUE)
    response.raise_for_status()
    return FetchedPage(
        url=str(response.url),
        content_type=response.headers.get("content-type", ""),
        body=response.content,
        by_browser=False,
    )
