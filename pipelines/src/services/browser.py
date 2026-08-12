from patchright.async_api import async_playwright


async def resolve_redirect(url: str) -> str:
    """Navigate with a real browser and return the final URL after all redirects
    (including JS). Falls back to the original URL on error."""
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch_persistent_context(
                user_data_dir="",
                channel="chrome",
                headless=False,
                no_viewport=True,
            )
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="commit", timeout=15000)
                return page.url
            finally:
                await browser.close()
    except Exception:
        return url
