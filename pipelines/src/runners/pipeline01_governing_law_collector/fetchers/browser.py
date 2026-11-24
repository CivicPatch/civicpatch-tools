"""A real browser, for a script-rendered page or a publisher's 403. It names itself as `plain` does, and
each main-frame navigation keeps to robots.txt and the host's pace."""

from http import HTTPStatus
from typing import Optional

import httpx
from patchright.async_api import Error as BrowserError, Page, async_playwright
from pydantic import BaseModel, ConfigDict

from . import plain
import services.browser as shared_browser
import services.polite as polite
from ..schemas import FetchedPage

HTML = "text/html"
NAVIGATION_TIMEOUT_MS = 30_000
SETTLE_MS = 3_000


class LoadedPage(BaseModel):
    model_config = ConfigDict(frozen=True)

    url: str
    # The first answer's: a challenge's 403, even when the challenge then clears.
    status: int
    first_title: str
    last_title: str
    content_type: str = HTML


async def fetch(url: str) -> FetchedPage:
    await polite.obey_host(url)
    async with async_playwright() as playwright:
        context = await shared_browser.open_browser(playwright)
        try:
            stopped = await shared_browser.guard_hops(context, url)
            page = await context.new_page()
            try:
                loaded = await _load(page, url)
            except BrowserError as error:
                if stopped:
                    raise stopped[0] from error
                # Callers already treat an httpx failure as "this url failed, move on".
                raise httpx.TransportError(f"{url}: {error}") from error
            failure = _failure(url, loaded)
            if failure:
                raise failure
            if shared_browser.is_pdf(loaded.content_type):
                body = await shared_browser.read_pdf(context, loaded.url)
                return FetchedPage(url=loaded.url, content_type=loaded.content_type, body=body, by_browser=True)
            return FetchedPage(url=loaded.url, content_type=HTML, body=(await page.content()).encode(), by_browser=True)
        finally:
            await context.close()


async def _load(page: Page, url: str) -> LoadedPage:
    response = await page.goto(url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
    first_title = await page.title()
    if shared_browser.is_challenge(first_title):
        await shared_browser.wait_out_challenge(page)
    await page.wait_for_timeout(SETTLE_MS)
    return LoadedPage(
        url=page.url,
        status=response.status if response else HTTPStatus.OK,
        first_title=first_title,
        last_title=await page.title(),
        content_type=(response.headers.get("content-type") if response else None) or HTML,
    )


def _failure(url: str, loaded: LoadedPage) -> Optional[Exception]:
    if shared_browser.is_challenge(loaded.last_title):
        return plain.RefusedByHost(loaded.url, loaded.status, challenged=True)
    if shared_browser.is_challenge(loaded.first_title):
        return None
    if loaded.status in plain.REFUSALS:
        return plain.RefusedByHost(loaded.url, loaded.status)
    if loaded.status >= HTTPStatus.BAD_REQUEST:
        return httpx.TransportError(f"{url} answered {loaded.status}")
    return None
