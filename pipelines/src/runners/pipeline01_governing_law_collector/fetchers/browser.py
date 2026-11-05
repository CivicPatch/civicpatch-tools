"""A real browser, for a script-rendered page or a publisher's 403. It names itself as `plain` does, and
each main-frame navigation keeps to robots.txt and the host's pace."""

from functools import partial
from http import HTTPStatus
from typing import List, Optional

import httpx
from patchright.async_api import Error as BrowserError, Page, Request, Route, async_playwright
from pydantic import BaseModel, ConfigDict

from . import plain
from ..schemas import FetchedPage

CHALLENGE_TITLE = "Just a moment..."
HTML = "text/html"
NAVIGATION_TIMEOUT_MS = 30_000
SETTLE_MS = 3_000
CHALLENGE_POLL_MS = 1_000
CHALLENGE_POLLS = 15


class LoadedPage(BaseModel):
    model_config = ConfigDict(frozen=True)

    url: str
    # The first answer's: a challenge's 403, even when the challenge then clears.
    status: int
    first_title: str
    last_title: str


async def fetch(url: str) -> FetchedPage:
    await plain.obey_host(url)
    stopped: List[plain.OffLimits] = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=False)
        try:
            # As pipeline 3 does: Chrome's own user agent. Announcing CivicPatchBot got whole sites refused.
            # context = await browser.new_context(user_agent=plain.USER_AGENT)
            context = await browser.new_context()
            await context.route("**/*", partial(_guard, url, stopped))
            page = await context.new_page()
            loaded = await _load(page, url)
            failure = _failure(url, loaded)
            if failure:
                raise failure
            return FetchedPage(url=loaded.url, content_type=HTML, body=(await page.content()).encode(), by_browser=True)
        except BrowserError as error:
            if stopped:
                raise stopped[0] from error
            # Callers already treat an httpx failure as "this url failed, move on".
            raise httpx.TransportError(f"{url}: {error}") from error
        finally:
            await browser.close()


async def _guard(first_url: str, stopped: List[plain.OffLimits], route: Route) -> None:
    """Appends to `stopped` because the browser aborts a blocked hop with a bare error: it is how
    `fetch` still reports why, such as DisallowedByRobots."""
    request = route.request
    if not _is_main_navigation(request):
        await (route.continue_() if plain.is_public_web_url(request.url) else route.abort())
        return
    blocked = await _blocked_hop(request.url, first_url)
    if blocked is None:
        await route.continue_()
        return
    stopped.append(blocked)
    await route.abort()


def _is_main_navigation(request: Request) -> bool:
    return request.is_navigation_request() and request.frame.parent_frame is None


async def _blocked_hop(url: str, first_url: str) -> Optional[plain.OffLimits]:
    """`fetch` has already checked the first url; a challenge reloading it needs no second turn."""
    if url == first_url:
        return None
    try:
        await plain.obey_host(url)
    except plain.OffLimits as off_limits:
        return off_limits
    return None


async def _load(page: Page, url: str) -> LoadedPage:
    response = await page.goto(url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
    first_title = await page.title()
    if first_title == CHALLENGE_TITLE:
        await _wait_out_challenge(page)
    await page.wait_for_timeout(SETTLE_MS)
    return LoadedPage(url=page.url, status=response.status if response else HTTPStatus.OK, first_title=first_title, last_title=await page.title())


async def _wait_out_challenge(page: Page) -> None:
    for _ in range(CHALLENGE_POLLS):
        await page.wait_for_timeout(CHALLENGE_POLL_MS)
        if await page.title() != CHALLENGE_TITLE:
            return


def _failure(url: str, loaded: LoadedPage) -> Optional[Exception]:
    if loaded.last_title == CHALLENGE_TITLE:
        return plain.RefusedByHost(loaded.url, loaded.status, challenged=True)
    if loaded.first_title == CHALLENGE_TITLE:
        return None
    if loaded.status in plain.REFUSALS:
        return plain.RefusedByHost(loaded.url, loaded.status)
    if loaded.status >= HTTPStatus.BAD_REQUEST:
        return httpx.TransportError(f"{url} answered {loaded.status}")
    return None
