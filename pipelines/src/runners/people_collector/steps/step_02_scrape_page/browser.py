from typing import Literal, TypedDict

from patchright.async_api import async_playwright

from runners.people_collector.steps.step_02_scrape_page.scrape_exceptions import NavigationError, NavigationFailureReason
from runners.people_collector.steps.step_02_scrape_page.scrape_constants import PAGE_DEFAULT_TIMEOUT_MS, PAGE_NAVIGATION_TIMEOUT_MS
from runners.people_collector.steps.step_02_scrape_page.scrape_wait import auto_detect_and_wait
from runners.people_collector.steps.step_02_scrape_page.scrape_dom import expand_accordions, flatten_shadow_root, html_relative_to_absolute_urls, inline_iframes
from runners.people_collector.steps.step_02_scrape_page.scrape_images import download_images


class ScrapeOptions(TypedDict):
    image_directory: str
    scraped_urls: list[str]
    accordion_keywords: list[str]


async def scrape(logger, website_url, options=None):
    options = options or {}
    timeout = options.get('timeout', PAGE_DEFAULT_TIMEOUT_MS)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch_persistent_context(
            user_data_dir="",
            channel="chrome",
            headless=False,
            no_viewport=True,
        )

        try:
            page = await browser.new_page()
            page.set_default_timeout(timeout)

            network_failure_reason = None
            def handle_request_failed(request):
                nonlocal network_failure_reason
                if request.url == website_url or request.url == website_url + "/":
                    if request.failure:
                        network_failure_reason = request.failure

            page.on("requestfailed", handle_request_failed)

            response = None
            last_errors: list[str] = []

            wait_until_strategies: list[Literal["networkidle", "load", "domcontentloaded"]] = ["networkidle", "load", "domcontentloaded"]
            for wait_until in wait_until_strategies:
                try:
                    response = await page.goto(website_url, wait_until=wait_until, timeout=PAGE_NAVIGATION_TIMEOUT_MS)
                    if response:
                        break
                except Exception as e:
                    last_errors.append(str(e))
                    logger.warning(f"Warning: navigation to {website_url} with wait_until={wait_until} failed: {e}")

            if response is None or not response.ok:
                http_status = response.status if response else None
                detailed_reason = (network_failure_reason or last_errors[-1] or "").upper()

                if http_status:
                    if http_status == 403:
                        reason = NavigationFailureReason.HTTP_403
                    elif http_status == 429:
                        reason = NavigationFailureReason.HTTP_429
                    elif http_status >= 500:
                        reason = NavigationFailureReason.HTTP_5XX
                    else:
                        reason = NavigationFailureReason.UNKNOWN
                else:
                    if "ERR_NAME_NOT_RESOLVED" in detailed_reason:
                        reason = NavigationFailureReason.NET_DNS_FAILURE
                    elif "ERR_CONNECTION_REFUSED" in detailed_reason:
                        reason = NavigationFailureReason.NET_CONNECTION_REFUSED
                    elif "ERR_ABORTED" in detailed_reason:
                        reason = NavigationFailureReason.NET_ABORTED
                    elif "TIMEOUT" in detailed_reason:
                        reason = NavigationFailureReason.NET_TIMEOUT
                    else:
                        reason = NavigationFailureReason.UNKNOWN

                logger.error(f"[{reason}] Failure at {website_url}. Detail: {detailed_reason}")
                raise NavigationError(website_url, reason, source=detailed_reason)

            scraped_urls = options.get('scraped_urls')
            if scraped_urls and page.url in scraped_urls:
                logger.info(f"Already scraped url: {website_url}, redirected to: {page.url}")
                raise ValueError("Already scraped this URL after redirect")

            accordion_keywords = options.get('accordion_keywords')
            await auto_detect_and_wait(page, logger, response)
            await expand_accordions(page, logger, accordion_keywords)
            await flatten_shadow_root(page)
            await html_relative_to_absolute_urls(page)
            await inline_iframes(page, logger)

            image_directory = options.get('image_directory')
            if image_directory:
                await download_images(browser, logger, page, image_directory)

            content = await page.content()
            return content, page.url

        finally:
            try:
                await browser.close()
            except Exception:
                pass
