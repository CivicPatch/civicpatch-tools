import asyncio
import ipaddress
import time
from http import HTTPStatus
from typing import Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from ..schemas import FetchedPage
from shared.utils.url_utils import is_web_url

# Named, so a host's operator can see who we are and how to reach us.
USER_AGENT = "CivicPatchBot/1.0 (+https://civicpatch.org)"
REFUSALS = {HTTPStatus.FORBIDDEN, HTTPStatus.TOO_MANY_REQUESTS}
CHALLENGE_HEADER = "cf-mitigated"
CHALLENGE_VALUE = "challenge"
ROBOTS_PATH = "/robots.txt"
# One request at a time to a host, this far apart unless its robots.txt asks for more.
PAUSE_SECONDS = 1.0
MAX_PAUSE_SECONDS = 10.0
ROBOTS_MAX_AGE_SECONDS = 86_400
# Process-wide on purpose: a host's rules and pace hold across every run in this worker.
_robots_by_origin: dict[str, tuple[float, Optional[RobotFileParser]]] = {}
_next_request_by_host: dict[str, float] = {}


class RefusedByHost(Exception):
    def __init__(self, url: str, status_code: int, *, challenged: bool = False):
        self.url = url
        self.status_code = status_code
        self.challenged = challenged
        super().__init__(f"{url} refused with {status_code}")


class OffLimits(Exception):
    """A url the collector never fetches: not http, no dotted host, or a bare IP address. The worker
    sits on the cluster, where a page or the model could otherwise point it at internal services."""

    def __init__(self, url: str):
        self.url = url
        super().__init__(f"{url} is off limits")


class DisallowedByRobots(OffLimits):
    """A url the host's robots.txt keeps from our bot."""


def is_public_web_url(url: str) -> bool:
    if not is_web_url(url):
        return False
    try:
        ipaddress.ip_address(urlparse(url).hostname or "")
    except ValueError:
        return True
    return False


async def _robots_of(origin: str) -> Optional[RobotFileParser]:
    """None when the host publishes no readable rules, which allows everything."""
    cached = _robots_by_origin.get(origin)
    if cached and time.monotonic() - cached[0] < ROBOTS_MAX_AGE_SECONDS:
        return cached[1]
    rules = None
    try:
        async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=30.0) as client:
            response = await client.get(origin + ROBOTS_PATH)
        if response.status_code == HTTPStatus.OK:
            rules = RobotFileParser()
            rules.parse(response.text.splitlines())
    except httpx.HTTPError:
        rules = None
    _robots_by_origin[origin] = (time.monotonic(), rules)
    return rules


async def _wait_for_turn(host: str, rules: Optional[RobotFileParser]) -> None:
    asked = rules.crawl_delay(USER_AGENT) if rules else None
    pause = min(float(asked), MAX_PAUSE_SECONDS) if asked else PAUSE_SECONDS
    now = time.monotonic()
    turn = max(now, _next_request_by_host.get(host, now))
    _next_request_by_host[host] = turn + pause
    if turn > now:
        await asyncio.sleep(turn - now)


async def _obey_request(request: httpx.Request) -> None:
    await obey_host(str(request.url))


async def obey_host(url: str) -> None:
    """Runs before every request, redirect hops included."""
    if not is_public_web_url(url):
        raise OffLimits(url)
    parsed = urlparse(url)
    rules = await _robots_of(f"{parsed.scheme}://{parsed.netloc}")
    if parsed.path != ROBOTS_PATH and rules and not rules.can_fetch(USER_AGENT, url):
        raise DisallowedByRobots(url)
    await _wait_for_turn(parsed.netloc, rules)


async def fetch(url: str) -> FetchedPage:
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=30.0, event_hooks={"request": [_obey_request]}
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
