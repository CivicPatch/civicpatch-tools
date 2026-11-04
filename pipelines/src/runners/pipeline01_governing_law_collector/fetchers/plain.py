import ipaddress
from http import HTTPStatus
from urllib.parse import urlparse

import httpx
from ..schemas import FetchedPage
from shared.utils.url_utils import is_web_url

# Named, so a host's operator can see who we are and how to reach us.
USER_AGENT = "CivicPatchBot/1.0 (+https://civicpatch.org)"
_REFUSALS = {HTTPStatus.FORBIDDEN, HTTPStatus.TOO_MANY_REQUESTS}


class RefusedByHost(Exception):
    def __init__(self, url: str, status_code: int):
        self.url = url
        self.status_code = status_code
        super().__init__(f"{url} refused with {status_code}")


class OffLimits(Exception):
    """A url the collector never fetches: not http, no dotted host, or a bare IP address. The worker
    sits on the cluster, where a page or the model could otherwise point it at internal services."""

    def __init__(self, url: str):
        self.url = url
        super().__init__(f"{url} is off limits")


def is_public_web_url(url: str) -> bool:
    if not is_web_url(url):
        return False
    try:
        ipaddress.ip_address(urlparse(url).hostname or "")
    except ValueError:
        return True
    return False


async def _refuse_off_limits(request: httpx.Request) -> None:
    """Runs before every request, redirect hops included."""
    if not is_public_web_url(str(request.url)):
        raise OffLimits(str(request.url))


async def fetch(url: str) -> FetchedPage:
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=30.0, event_hooks={"request": [_refuse_off_limits]}
    ) as client:
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
