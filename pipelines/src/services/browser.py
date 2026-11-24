"""The browser basics both pipelines that read the web share: one launch, robots and pace on every redirect
hop, a bot challenge waited out, and a PDF read through the browser's own session. A pipeline adds its own
page work on top."""

from functools import partial

from patchright.async_api import BrowserContext, Page, Playwright, Request, Route, async_playwright

import services.polite as polite

CHALLENGE_TITLE = "Just a moment..."
CHALLENGE_POLL_MS = 1_000
CHALLENGE_POLLS = 15
PDF = "pdf"
REDIRECT_TIMEOUT_MS = 15_000


async def open_browser(playwright: Playwright, launch_args: list[str] | None = None) -> BrowserContext:
    """Chrome, headed, with its own user agent: announcing CivicPatchBot got whole sites refused."""
    return await playwright.chromium.launch_persistent_context(
        user_data_dir="",
        channel="chrome",
        headless=False,
        no_viewport=True,
        args=launch_args or [],
    )


async def guard_hops(context: BrowserContext, first_url: str) -> list[polite.OffLimits]:
    """Every main-frame hop after `first_url` answers to robots.txt and the host's pace, and a page's other
    requests stay on the public web. The browser aborts a blocked hop with a bare error, so the returned list
    is how a caller still says why."""
    stopped: list[polite.OffLimits] = []
    await context.route("**/*", partial(_guard, first_url, stopped))
    return stopped


async def _guard(first_url: str, stopped: list[polite.OffLimits], route: Route) -> None:
    request = route.request
    if not _is_main_navigation(request):
        await (route.continue_() if polite.is_public_web_url(request.url) else route.abort())
        return
    if request.url == first_url:
        await route.continue_()
        return
    try:
        await polite.obey_host(request.url)
    except polite.OffLimits as off_limits:
        stopped.append(off_limits)
        await route.abort()
        return
    await route.continue_()


def _is_main_navigation(request: Request) -> bool:
    return request.is_navigation_request() and request.frame.parent_frame is None


def is_challenge(title: str) -> bool:
    return title == CHALLENGE_TITLE


async def wait_out_challenge(page: Page) -> None:
    """A bot challenge usually clears itself in a few seconds; this waits up to its limit, then returns either way."""
    for _ in range(CHALLENGE_POLLS):
        if not is_challenge(await page.title()):
            return
        await page.wait_for_timeout(CHALLENGE_POLL_MS)


def is_pdf(content_type: str) -> bool:
    return PDF in content_type.lower()


async def read_pdf(context: BrowserContext, url: str) -> bytes:
    """Chrome shows a PDF in its viewer, whose page is an empty shell; the file comes through the context's own
    request, which carries the cookies the navigation earned."""
    download = await context.request.get(url)
    return await download.body()


async def resolve_redirect(url: str) -> str:
    """The final url after every redirect, script ones included. The original url on any error."""
    try:
        async with async_playwright() as playwright:
            context = await open_browser(playwright)
            try:
                page = await context.new_page()
                await page.goto(url, wait_until="commit", timeout=REDIRECT_TIMEOUT_MS)
                return page.url
            finally:
                await context.close()
    except Exception:
        return url
